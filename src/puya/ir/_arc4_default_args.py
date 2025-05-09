import typing
from collections.abc import Mapping

import attrs

import puya.ir.models as ir
from puya import (
    artifact_metadata as models,
    log,
)
from puya.avm import OnCompletionAction
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.context import CompiledProgramProvider
from puya.errors import CodeError
from puya.ir._utils import make_subroutine
from puya.ir.arc4_types import get_arc4_name, maybe_wtype_to_arc4_wtype, wtype_to_arc4
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.optimize.main import get_subroutine_optimizations
from puya.options import PuyaOptions
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def convert_default_args(
    ctx: IRBuildContext,
    contract: awst_nodes.Contract,
    m: awst_nodes.ContractMethod,
    config: awst_nodes.ARC4ABIMethodConfig,
) -> Mapping[awst_nodes.SubroutineArgument, models.MethodArgDefault | None]:
    state_by_name = {s.member_name: s for s in contract.app_state}
    return {
        a: _convert_default_arg(
            ctx, contract, state_by_name, a, config.default_args.get(a.name), method_id=m.full_name
        )
        for a in m.args
    }


def _convert_default_arg(
    ctx: IRBuildContext,
    contract: awst_nodes.Contract,
    state_by_name: Mapping[str, awst_nodes.AppStorageDefinition],
    param: awst_nodes.SubroutineArgument,
    default: awst_nodes.ABIMethodArgDefault | None,
    *,
    method_id: str,
) -> models.MethodArgDefault | None:
    match default:
        case None:
            return None
        case awst_nodes.ABIMethodArgMemberDefault(name=member_name):
            result_or_error = _convert_member_arg_default(
                contract, state_by_name, param, member_name
            )
            match result_or_error:
                case str(error_message):
                    logger.error(error_message, location=param.source_location)
                    return None
                case result:
                    return result
        case awst_nodes.ABIMethodArgConstantDefault(value=expr):
            return _compile_arc4_default_constant(ctx, method_id, param, expr)


def _convert_member_arg_default(
    contract: awst_nodes.Contract,
    state_by_name: Mapping[str, awst_nodes.AppStorageDefinition],
    param: awst_nodes.SubroutineArgument,
    member_name: str,
) -> models.MethodArgDefaultFromState | models.MethodArgDefaultFromMethod | str:
    if (state_source := state_by_name.get(member_name)) is not None:
        if state_source.key_wtype is not None:
            return "state member is a map"
        return models.MethodArgDefaultFromState(
            kind=state_source.kind,
            key=state_source.key.value,
            key_type=(
                "AVMString"
                if state_source.key.encoding == awst_nodes.BytesEncoding.utf8
                else "AVMBytes"
            ),
        )
    elif (method_source := contract.resolve_contract_method(member_name)) is not None:
        abi_method_config = method_source.arc4_method_config
        if not isinstance(abi_method_config, awst_nodes.ARC4ABIMethodConfig):
            return "only ARC-4 ABI methods can be used as default values"
        if OnCompletionAction.NoOp not in abi_method_config.allowed_completion_types:
            return f"{member_name!r} does not allow no_op on completion calls"
        if abi_method_config.create == awst_nodes.ARC4CreateOption.require:
            return f"{member_name!r} can only be used for create calls"
        if not abi_method_config.readonly:
            return f"{member_name!r} is not readonly"
        if method_source.args:
            return f"{member_name!r} does not take zero arguments"
        if method_source.return_type == wtypes.void_wtype:
            return f"{member_name!r} does not provide a value"
        # return is used here so reference types are treated as their ARC-4 encoded equivalents
        param_arc4_type = wtype_to_arc4("return", param.wtype, param.source_location)
        return_type_arc4 = wtype_to_arc4(
            "return", method_source.return_type, method_source.source_location
        )
        if return_type_arc4 != param_arc4_type:
            return f"{method_source.member_name!r} does not provide {param_arc4_type!r} type"
        return models.MethodArgDefaultFromMethod(
            name=abi_method_config.name,
            return_type=return_type_arc4,
            readonly=abi_method_config.readonly,
        )
    else:
        return f"{member_name!r} is not a known state or method attribute"


def _compile_arc4_default_constant(
    ctx: IRBuildContext,
    method_id: str,
    param: awst_nodes.SubroutineArgument,
    expr: awst_nodes.Expression,
) -> models.MethodArgDefaultConstant | None:
    location = expr.source_location
    logger.debug("Building IR for ARC-4 method argument default constant", location=location)

    if param.wtype != expr.wtype:
        logger.error("mismatch between parameter type and default value type", location=location)
        return None

    if isinstance(expr.wtype, wtypes.ARC4Type):
        arc4_wtype = expr.wtype
    else:
        arc4_type = maybe_wtype_to_arc4_wtype(expr.wtype)
        if arc4_type is None:
            logger.error("unsupported type for argument default", location=location)
            return None
        expr = awst_nodes.ARC4Encode(value=expr, wtype=arc4_type, source_location=location)
        arc4_wtype = arc4_type

    arc4_type_name = get_arc4_name(arc4_wtype, use_alias=True)

    fake_name = f"#default:{param.name}"
    awst_subroutine = awst_nodes.Subroutine(
        id=method_id + fake_name,
        name=fake_name,
        source_location=expr.source_location,
        args=[],
        return_type=expr.wtype,
        body=awst_nodes.Block(
            body=[awst_nodes.ReturnStatement(value=expr, source_location=expr.source_location)],
            source_location=expr.source_location,
        ),
        documentation=awst_nodes.MethodDocumentation(),
        inline=False,
    )
    ir_subroutine = make_subroutine(awst_subroutine, allow_implicits=False)
    FunctionIRBuilder.build_body(ctx, awst_subroutine, ir_subroutine)

    bytes_result = _try_extract_byte_constant(ir_subroutine)
    if bytes_result is None:
        _optimize_subroutine(ctx, ir_subroutine, location)
        bytes_result = _try_extract_byte_constant(ir_subroutine)
    if bytes_result is None:
        logger.error("could not determine constant value", location=location)
        return None
    return models.MethodArgDefaultConstant(data=bytes_result, type_=arc4_type_name)


def _optimize_subroutine(
    ctx: IRBuildContext, subroutine: ir.Subroutine, location: SourceLocation
) -> None:
    optimization_level = max(2, ctx.options.optimization_level)
    logger.debug(
        f"Running optimizer at level {optimization_level}"
        f" to encode compile time constant to bytes",
        location=location,
    )
    options = PuyaOptions(
        optimization_level=optimization_level,
        target_avm_version=ctx.options.target_avm_version,
    )
    dummy_program_provider = _NoCompiledProgramProvider(location)
    pass_context = IROptimizationContext(
        compilation_set=ctx.compilation_set,
        sources_by_path=ctx.sources_by_path,
        options=options,
        compiled_program_provider=dummy_program_provider,
        output_path_provider=None,
        expand_all_bytes=True,
    )
    pipeline = get_subroutine_optimizations(optimization_level=optimization_level)
    while True:
        modified = False
        for optimizer in pipeline:
            if optimizer.optimize(pass_context, subroutine):
                modified = True
        if not modified:
            return


def _try_extract_byte_constant(subroutine: ir.Subroutine) -> bytes | None:
    match subroutine.body:
        case [
            ir.BasicBlock(
                phis=[],
                ops=[],
                terminator=ir.SubroutineReturn(result=[ir.BytesConstant(value=result)]),
            )
        ]:
            return result
    return None


@attrs.frozen
class _NoCompiledProgramProvider(CompiledProgramProvider):
    source_location: SourceLocation

    @typing.override
    def build_program_bytecode(self, *args: object, **kwargs: object) -> typing.Never:
        raise CodeError(
            "compilation references are not supported as method default constants",
            self.source_location,
        )

    @typing.override
    def get_state_totals(self, *args: object, **kwargs: object) -> typing.Never:
        raise CodeError(
            "compilation references are not supported as method default constants",
            self.source_location,
        )
