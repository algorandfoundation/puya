import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, IndexExpression, NewArray, UInt64Constant
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import GenericTypeBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

__all__ = [
    "StaticArrayGenericTypeBuilder",
    "StaticArrayTypeBuilder",
    "StaticArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class StaticArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        element_type = expect.instance_builder(args[0], default=expect.default_raise).pytype
        array_size = len(args)
        typ = pytypes.GenericARC4StaticArrayType.parameterise(
            [element_type, pytypes.TypingLiteralType(value=array_size, source_location=None)],
            location,
        )
        values = tuple(expect.argument_of_type_else_dummy(a, element_type).resolve() for a in args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), typ
        )


class StaticArrayTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4StaticArrayType
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
        n_args = expect.exactly_n_args_of_type_else_dummy(args, typ.items, location, self._size)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(
                values=tuple(arg.resolve() for arg in n_args),
                wtype=wtype,
                source_location=location,
            ),
            typ,
        )


class StaticArrayExpressionBuilder(_ARC4ArrayExpressionBuilder, StaticSizedCollectionBuilder):
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
                    source_location=self.source_location,
                ),
            )
            for idx in range(self._size)
        ]
