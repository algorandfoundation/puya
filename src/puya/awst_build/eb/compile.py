from __future__ import annotations

import itertools
import typing

import mypy.nodes
import mypy.types

from puya.awst.nodes import (
    CompiledContract,
    CompiledLogicSig,
    Expression,
    TupleExpression,
    TupleItemExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import (
    FunctionBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puya.awst_build.eb.dict_ import DictLiteralBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.errors import CodeError
from puya.log import get_logger
from puya.models import CompiledReferenceField, ContractReference, LogicSigReference

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from puya.parse import SourceLocation

logger = get_logger(__name__)

_ALLOCATION_OVERRIDE_FIELDS = (
    CompiledReferenceField.extra_program_pages,
    CompiledReferenceField.global_uints,
    CompiledReferenceField.global_bytes,
    CompiledReferenceField.local_uints,
    CompiledReferenceField.local_bytes,
)


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


class CompileContractFunctionBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self.produces = pytypes.CompiledContractType

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        type_reference, kwargs = _single_positional_and_kwargs(arg_names, args, location)
        match type_reference:
            case NodeBuilder(
                pytype=pytypes.TypeType(typ=typ)
            ) if pytypes.ContractBaseType in typ.mro:
                module_name, class_name = typ.name.rsplit(".", maxsplit=1)
                contract = ContractReference(
                    module_name=module_name,
                    class_name=class_name,
                )
            case None:
                return dummy_value(self.produces, location)
            case _:
                logger.error("invalid contract reference", location=type_reference.source_location)
                return dummy_value(self.produces, location)

        prefix, template_vars = _extract_prefix_template_args(kwargs)
        allocation_overrides = _extract_allocation_overrides(kwargs)
        _expect_empty(kwargs.values())

        return CompiledContractExpressionBuilder(
            CompiledContract(
                contract=contract,
                allocation_overrides=allocation_overrides,
                prefix=prefix,
                template_variables=template_vars,
                wtype=self.produces.wtype,
                source_location=location,
            )
        )


class CompileLogicSigFunctionBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self.produces = pytypes.CompiledLogicSigType

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        type_reference, kwargs = _single_positional_and_kwargs(arg_names, args, location)
        logic_sig = LogicSigReference("", "")
        match type_reference:
            case LogicSigExpressionBuilder(ref=logic_sig):
                pass
            case None:
                pass
            case _:
                logger.error("invalid logicsig reference", location=type_reference.source_location)

        prefix, template_vars = _extract_prefix_template_args(kwargs)
        _expect_empty(kwargs.values())

        return CompiledLogicSigExpressionBuilder(
            CompiledLogicSig(
                logic_sig=logic_sig,
                prefix=prefix,
                template_variables=template_vars,
                wtype=self.produces.wtype,
                source_location=location,
            )
        )


def _extract_allocation_overrides(
    name_args: dict[str, NodeBuilder]
) -> Mapping[CompiledReferenceField, Expression]:
    allocation_overrides = dict[CompiledReferenceField, Expression]()
    for field in _ALLOCATION_OVERRIDE_FIELDS:
        if arg := name_args.pop(field, None):
            allocation_overrides[field] = expect.exactly_one_arg_of_type_else_dummy(
                [arg], pytypes.UInt64Type, location=arg.source_location, resolve_literal=True
            ).resolve()
    return allocation_overrides


def _extract_prefix_template_args(
    name_args: dict[str, NodeBuilder]
) -> tuple[str | None, Mapping[str, Expression]]:
    prefix: str | None = None
    template_vars: Mapping[str, Expression] = {}

    if template_vars_node := name_args.pop("template_vars", None):
        if isinstance(template_vars_node, DictLiteralBuilder):
            template_vars = {k: v.resolve() for k, v in template_vars_node.mapping.items()}
        else:
            logger.error("unexpected argument type", location=template_vars_node.source_location)
    if prefix_node := name_args.pop("template_vars_prefix", None):
        prefix = expect.simple_string_literal(
            prefix_node, default=expect.default_fixed_value(None)
        )
    return prefix, template_vars


def _single_positional_and_kwargs(
    names: Sequence[str | None], args: Sequence[NodeBuilder], location: SourceLocation
) -> tuple[NodeBuilder | None, dict[str, NodeBuilder]]:
    positional: NodeBuilder | None = None
    kwargs = dict[str, NodeBuilder]()
    for name, arg in zip(names, args, strict=True):
        if name is None:
            if positional:
                logger.error("unexpected argument", location=arg.source_location)
            else:
                positional = arg
        else:
            kwargs[name] = arg
    if positional is None:
        logger.error("expected 1 positional arg", location=location)
    return positional, kwargs


def _expect_empty(args: Iterable[NodeBuilder]) -> None:
    for arg in args:
        logger.error("unexpected argument", location=arg.source_location)
