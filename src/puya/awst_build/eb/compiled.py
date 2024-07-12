import itertools
import typing
from collections.abc import Mapping, Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import (
    CompiledContract,
    CompiledLogicSig,
    Expression,
    TupleExpression,
    TupleItemExpression,
)
from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puya.awst_build.eb.dict_ import DictLiteralBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
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


class _LinearizedNamedTuple(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression, pytype: pytypes.TupleType):
        names = pytype.names
        assert names is not None
        self._item_map = {name: (idx, pytype.items[idx]) for idx, name in enumerate(names)}
        super().__init__(pytype, expr)

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        try:
            item_index, item_type = self._item_map[name]
        except KeyError:
            return super().member_access(name, location)
        if isinstance(item_type, pytypes.TupleType):
            return self._read_tuple_slice(item_index, item_type, location)
        else:
            return self._read_tuple_index(item_index, item_type, location)

    def _read_tuple_slice(
        self, item_index: int, item_type: pytypes.TupleType, location: SourceLocation
    ) -> InstanceBuilder:
        start_index = self._get_linear_index(item_index)
        end_index = start_index + _get_linear_tuple_size(item_type)
        expr = self.resolve()
        return TupleExpressionBuilder(
            TupleExpression.from_items(
                [
                    TupleItemExpression(base=expr, index=index, source_location=location)
                    for index in range(start_index, end_index)
                ],
                location,
            ),
            item_type,
        )

    def _read_tuple_index(
        self, item_index: int, item_type: pytypes.PyType, location: SourceLocation
    ) -> InstanceBuilder:
        return builder_for_instance(
            item_type,
            TupleItemExpression(
                base=self.resolve(),
                index=self._get_linear_index(item_index),
                source_location=location,
            ),
        )

    def _get_linear_index(self, index: int) -> int:
        length = 0
        for _, item_type in itertools.islice(self._item_map.values(), index):
            length += _get_linear_tuple_size(item_type)
        return length


def _get_linear_tuple_size(pytyp: pytypes.PyType) -> int:
    if isinstance(pytyp, pytypes.TupleType):
        return sum(map(_get_linear_tuple_size, pytyp.items))
    return 1


class CompiledContractExpressionBuilder(_LinearizedNamedTuple):
    def __init__(self, expr: Expression) -> None:
        super().__init__(expr, pytypes.CompiledContractType)


class CompiledLogicSigExpressionBuilder(_LinearizedNamedTuple):
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
            case NodeBuilder(
                pytype=pytypes.TypeType(typ=typ)
            ) if pytypes.ContractBaseType in typ.mro:
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
