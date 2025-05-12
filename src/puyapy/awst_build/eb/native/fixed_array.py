import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Copy,
    Expression,
    IndexExpression,
    NewArray,
    UInt64Constant,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import GenericTypeBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance, builder_for_type
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
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
        arg = expect.at_most_one_arg(args, location)
        if not arg:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        # TODO: check arg type is sequence like not just iterable
        element_type = arg.iterable_item_type()
        if isinstance(arg.pytype, pytypes.ArrayType) and arg.pytype.size is not None:
            size = arg.pytype.size
        elif isinstance(arg.pytype, pytypes.TupleType):
            size = len(arg.pytype.items)
        else:
            raise CodeError("FixedArray requires a length type parameter", location)
        size_literal = pytypes.TypingLiteralType(value=size, source_location=None)
        typ = pytypes.GenericFixedArrayType.parameterise([element_type, size_literal], location)
        wtype = typ.checked_wtype(location)
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return FixedArrayExpressionBuilder(
            ARC4Encode(
                value=arg.resolve(),
                wtype=wtype,
                source_location=location,
            ),
            typ,
        )


class FixedArrayTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericFixedArrayType
        assert typ.size is not None
        self._size = typ.size
        super().__init__(typ, location)

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
        assert typ.size is not None
        arg = expect.at_most_one_arg(args, location)
        # TODO: check arg type is sequence like not just iterable

        if not arg:
            default_elements = [
                builder_for_type(typ.items, location)
                .call(
                    [],
                    arg_kinds=[],
                    arg_names=[],
                    location=location,
                )
                .resolve()
                for _ in range(typ.size)
            ]
            new_array: Expression = NewArray(
                values=default_elements,
                wtype=wtype,
                source_location=location,
            )
        elif arg.pytype == typ:
            new_array = Copy(
                value=arg.resolve(),
                source_location=location,
            )
        else:
            new_array = ARC4Encode(
                value=arg.resolve(),
                wtype=wtype,
                source_location=location,
            )
        return FixedArrayExpressionBuilder(new_array, typ)


class FixedArrayExpressionBuilder(_ARC4ArrayExpressionBuilder, StaticSizedCollectionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
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
