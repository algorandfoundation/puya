import typing
from collections.abc import Mapping

import attrs

import puya.ir.models as ir
from puya import (
    artifact_metadata as models,
    log,
)
from puya.avm import AVMType, OnCompletionAction
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.arc4_types import maybe_avm_to_arc4_equivalent_type, wtype_to_arc4
from puya.context import ArtifactCompileContext, CompiledProgramProvider
from puya.errors import CodeError
from puya.ir._utils import make_subroutine
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.ir.optimize.main import optimize_program_ir
from puya.parse import SourceLocation
from puya.program_refs import ProgramKind
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


def convert_default_args(
    ctx: IRBuildContext,
    contract: awst_nodes.Contract,
    m: awst_nodes.ContractMethod,
    config: awst_nodes.ARC4ABIMethodConfig,
) -> Mapping[awst_nodes.SubroutineArgument, models.MethodArgDefault | None]:
    state_by_name = {s.member_name: s for s in contract.app_state}
    return {
        a: _convert_default_arg(ctx, contract, state_by_name, a, config.default_args.get(a.name))
        for a in m.args
    }


def _convert_default_arg(
    ctx: IRBuildContext,
    contract: awst_nodes.Contract,
    state_by_name: Mapping[str, awst_nodes.AppStorageDefinition],
    arg: awst_nodes.SubroutineArgument,
    default: awst_nodes.ABIMethodArgDefault | None,
) -> models.MethodArgDefault | None:
    match default:
        case None:
            return None
        case awst_nodes.ABIMethodArgMemberDefault(name=member_name):
            result_or_error = _convert_member_arg_default(
                contract, state_by_name, arg, member_name
            )
            match result_or_error:
                case str(error_message):
                    logger.error(error_message, location=arg.source_location)
                    return None
                case result:
                    return result
        case awst_nodes.ABIMethodArgConstantDefault(value=expr):
            return _compile_arc4_default_constant(ctx, expr)


def _convert_member_arg_default(
    contract: awst_nodes.Contract,
    state_by_name: Mapping[str, awst_nodes.AppStorageDefinition],
    param: awst_nodes.SubroutineArgument,
    member_name: str,
) -> models.MethodArgDefaultFromState | models.MethodArgDefaultFromMethod | str:
    param_arc4_type = wtype_to_arc4(param.wtype)

    # special handling for reference types
    match param_arc4_type:
        case "asset" | "application":
            param_arc4_type = "uint64"
        case "account":
            param_arc4_type = "address"

    if (state_source := state_by_name.get(member_name)) is not None:
        if state_source.key_wtype is not None:
            return "state member is a map"
        storage_type = wtypes.persistable_stack_type(
            state_source.storage_wtype, param.source_location
        )
        if (
            storage_type is AVMType.uint64
            # storage can provide an int to types <= uint64
            # TODO: check what ATC does with ufixed, see if it can be added
            and not (param_arc4_type == "byte" or param_arc4_type.startswith("uint"))
        ) or (
            storage_type is AVMType.bytes
            # storage can provide fixed byte arrays
            and not (
                param_arc4_type == "address"
                or (param_arc4_type.startswith("byte[") and param_arc4_type != "byte[]")
            )
        ):
            return f"{member_name!r} cannot provide {param_arc4_type!r} type"
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
        if method_source.return_type is wtypes.void_wtype:
            return f"{member_name!r} does not provide a value"
        return_type_arc4 = wtype_to_arc4(method_source.return_type)
        if return_type_arc4 != param_arc4_type:
            return f"{member_name!r} does not provide {param_arc4_type!r} type"
        return models.MethodArgDefaultFromMethod(
            name=abi_method_config.name,
            return_type=return_type_arc4,
            readonly=abi_method_config.readonly,
        )
    else:
        return f"{member_name!r} is not a known state or method attribute"


def _compile_arc4_default_constant(
    ctx: IRBuildContext, expr: awst_nodes.Expression
) -> models.MethodArgDefaultConstant | None:
    match expr.wtype:
        case wtypes.ARC4Type() as arc4_type:
            pass
        case other:
            converted = maybe_avm_to_arc4_equivalent_type(other)
            if converted is None:
                logger.error(
                    "unsupported type for argument default", location=expr.source_location
                )
                return None
            arc4_type = converted
            expr = awst_nodes.ARC4Encode(
                value=expr,
                wtype=converted,
                source_location=expr.source_location,
            )
    # TODO: compare type with parameter type

    awst_subroutine = awst_nodes.Subroutine(
        id="",
        name="",
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

    program = ir.Program(
        kind=ProgramKind.logic_signature,
        main=ir_subroutine,
        subroutines=[],
        avm_version=ctx.options.target_avm_version,
    )

    artifact_context = attrs_extend(
        ArtifactCompileContext,
        ctx,
        compiled_program_provider=_NoCompiledProgramProvider(expr.source_location),
        output_path_provider=None,
        options=attrs.evolve(ctx.options, optimization_level=2, output_optimization_ir=False),
    )

    optimize_program_ir(artifact_context, program, expand_all_bytes=True, routable_method_ids=None)

    match ir_subroutine.body:
        case [
            ir.BasicBlock(
                phis=[],
                ops=[],
                terminator=ir.SubroutineReturn(result=[ir.BytesConstant(value=result)]),
            )
        ]:
            return models.MethodArgDefaultConstant(data=result, type_=arc4_type.name)

    logger.error("unsupported method default constant", location=expr.source_location)
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
