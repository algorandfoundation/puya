import typing
from collections.abc import Mapping, Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import (
    CompiledContract,
    CompiledLogicSig,
    Expression,
)
from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.dict_ import DictLiteralBuilder
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puya.awst_build.eb.named_tuple import NamedTupleExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.log import get_logger
from puya.models import ContractReference, LogicSigReference
from puya.parse import SourceLocation

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


_TEMPLATE_VAR_KWARG_NAMES = [
    "template_vars",
    "template_vars_prefix",
]


class CompileContractFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
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
            case NodeBuilder(pytype=pytypes.TypeType(typ=typ)) if pytypes.ContractBaseType < typ:
                module_name, class_name = typ.name.rsplit(".", maxsplit=1)
                contract = ContractReference(
                    module_name=module_name,
                    class_name=class_name,
                )
            case invalid_or_none:
                # if None (=missing), then error message already logged by get_arg_mapping
                if invalid_or_none is not None:
                    logger.error(
                        "unexpected argument type", location=invalid_or_none.source_location
                    )
                return dummy_value(result_type, location)

        return NamedTupleExpressionBuilder(
            CompiledContract(
                contract=contract,
                allocation_overrides=allocation_overrides,
                prefix=prefix,
                template_variables=template_vars,
                wtype=result_type.wtype,
                source_location=location,
            ),
            result_type,
        )


class CompileLogicSigFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
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
                logic_sig = LogicSigReference("", "")  # dummy reference
                # if None (=missing), then error message already logged by get_arg_mapping
                if missing_or_invalid is not None:
                    logger.error(
                        "unexpected argument type", location=missing_or_invalid.source_location
                    )
        result_type = pytypes.CompiledLogicSigType
        prefix, template_vars = _extract_prefix_template_args(arg_map)
        return NamedTupleExpressionBuilder(
            CompiledLogicSig(
                logic_sig=logic_sig,
                prefix=prefix,
                template_variables=template_vars,
                wtype=result_type.wtype,
                source_location=location,
            ),
            result_type,
        )


def _extract_prefix_template_args(
    name_args: dict[str, NodeBuilder]
) -> tuple[str | None, Mapping[str, Expression]]:
    prefix: str | None = None
    template_vars: Mapping[str, Expression] = {}

    if template_vars_node := name_args.get("template_vars"):
        if isinstance(template_vars_node, DictLiteralBuilder):
            template_vars = {k: v.resolve() for k, v in template_vars_node.mapping.items()}
        else:
            logger.error("unexpected argument type", location=template_vars_node.source_location)
    if prefix_node := name_args.get("template_vars_prefix"):
        prefix = expect.simple_string_literal(prefix_node, default=expect.default_none)
    return prefix, template_vars
