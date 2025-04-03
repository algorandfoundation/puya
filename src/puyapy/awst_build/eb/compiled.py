import typing
from collections.abc import Mapping, Sequence

from puya.awst.nodes import CompiledContract, CompiledLogicSig, Expression
from puya.awst.txn_fields import TxnField
from puya.log import get_logger
from puya.parse import SourceLocation
from puya.program_refs import LogicSigReference
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.dict_ import DictLiteralBuilder
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = get_logger(__name__)

# these names should match pytypes CompiledContract definition
PROGRAM_FIELDS = {
    "approval_program": TxnField.ApprovalProgramPages,
    "clear_state_program": TxnField.ClearStateProgramPages,
}
APP_ALLOCATION_FIELDS = {
    "extra_program_pages": TxnField.ExtraProgramPages,
    "global_bytes": TxnField.GlobalNumByteSlice,
    "global_uints": TxnField.GlobalNumUint,
    "local_bytes": TxnField.LocalNumByteSlice,
    "local_uints": TxnField.LocalNumUint,
}


class CompiledContractExpressionBuilder(TupleExpressionBuilder):
    def __init__(self, expr: Expression) -> None:
        super().__init__(expr, pytypes.CompiledContractType)


class CompiledLogicSigExpressionBuilder(TupleExpressionBuilder):
    def __init__(self, expr: Expression) -> None:
        super().__init__(expr, pytypes.CompiledLogicSigType)


_TEMPLATE_VAR_KWARG_NAMES = [
    "template_vars",
    "template_vars_prefix",
]


class CompileContractFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        contract_arg_name = "contract"
        arg_map, _ = get_arg_mapping(
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
            required_positional_names=[contract_arg_name],
            optional_kw_only=[
                *APP_ALLOCATION_FIELDS,
                *_TEMPLATE_VAR_KWARG_NAMES,
            ],
        )
        prefix, template_vars = _extract_prefix_template_args(arg_map)
        allocation_overrides = {}
        for python_name, field in APP_ALLOCATION_FIELDS.items():
            if arg := arg_map.get(python_name):
                allocation_overrides[field] = expect.argument_of_type_else_dummy(
                    arg, pytypes.UInt64Type, resolve_literal=True
                ).resolve()

        result_type = pytypes.CompiledContractType
        match arg_map[contract_arg_name]:
            case NodeBuilder(pytype=pytypes.TypeType(typ=pytypes.ContractType() as contract_typ)):
                contract = contract_typ.name
            case invalid_or_none:
                if invalid_or_none is None:
                    # if None (=missing), then error message already logged by get_arg_mapping
                    return dummy_value(result_type, location)
                return expect.not_this_type(
                    invalid_or_none, default=expect.default_dummy_value(result_type)
                )

        return CompiledContractExpressionBuilder(
            CompiledContract(
                contract=contract,
                allocation_overrides=allocation_overrides,
                prefix=prefix,
                template_variables=template_vars,
                wtype=result_type.wtype,
                source_location=location,
            )
        )


class CompileLogicSigFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        logicsig_arg_name = "logicsig"
        arg_map, _ = get_arg_mapping(
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
            required_positional_names=[logicsig_arg_name],
            optional_kw_only=_TEMPLATE_VAR_KWARG_NAMES,
        )
        match arg_map.get(logicsig_arg_name):
            case LogicSigExpressionBuilder(ref=logic_sig):
                pass
            case missing_or_invalid:
                logic_sig = LogicSigReference("")  # dummy reference
                # if None (=missing), then error message already logged by get_arg_mapping
                if missing_or_invalid is not None:
                    expect.not_this_type(missing_or_invalid, default=expect.default_none)
        prefix, template_vars = _extract_prefix_template_args(arg_map)
        return CompiledLogicSigExpressionBuilder(
            CompiledLogicSig(
                logic_sig=logic_sig,
                prefix=prefix,
                template_variables=template_vars,
                wtype=pytypes.CompiledLogicSigType.wtype,
                source_location=location,
            )
        )


def _extract_prefix_template_args(
    name_args: dict[str, NodeBuilder],
) -> tuple[str | None, Mapping[str, Expression]]:
    prefix: str | None = None
    template_vars: Mapping[str, Expression] = {}

    if template_vars_node := name_args.get("template_vars"):
        if isinstance(template_vars_node, DictLiteralBuilder):
            template_vars = {k: v.resolve() for k, v in template_vars_node.mapping.items()}
        else:
            expect.not_this_type(template_vars_node, default=expect.default_none)
    if prefix_node := name_args.get("template_vars_prefix"):
        prefix = expect.simple_string_literal(prefix_node, default=expect.default_none)
    return prefix, template_vars
