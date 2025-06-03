import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Copy, Expression, IndexExpression, NewArray, UInt64Constant
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.native._base import _ArrayExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

__all__ = [
    "FixedArrayGenericTypeBuilder",
    "FixedArrayTypeBuilder",
    "FixedArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class FixedArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("FixedArray usage requires type parameters", location)


class FixedArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericFixedArrayType
        assert typ.size is not None
        self._size = typ.size
        super().__init__(typ, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "full":
            return _Full(self.produces(), self._size, location)
        return super().member_access(name, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        arg = expect.exactly_one_arg(args, location, default=expect.default_dummy_value(typ))
        arg_item_type = arg.iterable_item_type()
        if not (typ.items <= arg_item_type):
            logger.error(
                "iterable element type does not match collection type",
                location=arg.source_location,
            )
            return dummy_value(typ, location)

        if arg.pytype.wtype == wtype:
            new_array: Expression = Copy(value=arg.resolve(), source_location=location)
        elif isinstance(arg, StaticSizedCollectionBuilder):
            item_builders = arg.iterate_static()
            if len(item_builders) != self._size:
                logger.error("argument has incorrect length", location=arg.source_location)
            items = [ib.resolve() for ib in item_builders]
            new_array = NewArray(values=items, wtype=wtype, source_location=location)
        else:
            logger.error("unsupported collection type", location=arg.source_location)
            return dummy_value(typ, location)
        return FixedArrayExpressionBuilder(new_array, typ)


class FixedArrayExpressionBuilder(_ArrayExpressionBuilder, StaticSizedCollectionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericFixedArrayType
        size = typ.size
        assert size is not None
        self._size = size
        super().__init__(typ, expr)

    @typing.override
    def length(self, location: SourceLocation) -> InstanceBuilder:
        return UInt64ExpressionBuilder(UInt64Constant(value=self._size, source_location=location))

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=self._size > 0, location=location, negate=negate)

    @typing.override
    def iterate_static(self) -> Sequence[InstanceBuilder]:
        base = self.single_eval().resolve()
        return [
            builder_for_instance(
                self.pytype.items,
                IndexExpression(
                    base=base,
                    index=UInt64Constant(value=idx, source_location=self.source_location),
                    wtype=self.pytype.items_wtype,
                    source_location=self.source_location,
                ),
            )
            for idx in range(self._size)
        ]


class _Full(FunctionBuilder):
    def __init__(self, array_type: pytypes.ArrayType, size: int, location: SourceLocation):
        super().__init__(location=location)
        self._array_type = array_type
        self._size = size

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, self._array_type.items, location)
        arg = arg.single_eval()
        wtype = self._array_type.checked_wtype(location)
        assert isinstance(wtype, wtypes.ARC4StaticArray), "expected ARC4StaticArray"

        new_array: Expression = NewArray(
            values=[
                Copy(value=arg.resolve(), source_location=location) for _ in range(self._size)
            ],
            wtype=wtype,
            source_location=location,
        )
        return builder_for_instance(self._array_type, new_array)
