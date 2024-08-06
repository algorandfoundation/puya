import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import Expression, TupleExpression, TupleItemExpression
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.log import get_logger
from puya.parse import SourceLocation

logger = get_logger(__name__)

__all__ = [
    "NamedTupleTypeBuilder",
    "NamedTupleExpressionBuilder",
]


class NamedTupleTypeBuilder(TypeBuilder[pytypes.NamedTupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.NamedTupleType)
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.produces()
        field_mapping, any_missing = get_arg_mapping(
            required_positional_names=list(pytype.fields),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(pytype, location)

        items = [
            expect.argument_of_type_else_dummy(field_mapping[field_name], field_type).resolve()
            for field_name, field_type in pytype.fields.items()
        ]
        expr = TupleExpression(wtype=pytype.wtype, items=items, source_location=location)
        return NamedTupleExpressionBuilder(expr, pytype)


class _EmptyNamedTuple(typing.NamedTuple):
    pass


_NAMED_TUPLE_METHODS: typing.Final = dir(_EmptyNamedTuple())


class NamedTupleExpressionBuilder(TupleExpressionBuilder):
    def __init__(self, expr: Expression, pytype: pytypes.PyType):
        assert isinstance(pytype, pytypes.NamedTupleType)
        self._field_info = {
            name: (idx, typ) for idx, (name, typ) in enumerate(pytype.fields.items())
        }
        super().__init__(expr, pytype)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        try:
            item_index, item_type = self._field_info[name]
        except KeyError:
            if name in _NAMED_TUPLE_METHODS:
                raise CodeError("method is not currently supported", location) from None
            return super().member_access(name, location)
        # TODO: field access instead
        expr = TupleItemExpression(
            base=self.resolve(),
            index=item_index,
            source_location=location,
        )
        return builder_for_instance(item_type, expr)
