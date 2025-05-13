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
from puyapy.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    TypeBuilder,
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


class FixedArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericFixedArrayType
        assert typ.size is not None
        self._size = typ.size
        self._array_type = typ
        super().__init__(typ, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "full":
            return _Full(self._array_type, self._size, location)
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
        assert typ.size is not None
        arg = expect.exactly_one_arg(args, location, default=expect.default_dummy_value(typ))
        # TODO: check arg type is sequence like not just iterable

        if arg.pytype == typ:
            new_array: Expression = Copy(
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


# TODO: consider if depending on _ARC4ArrayExpressionBuilder is appropriate here
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
