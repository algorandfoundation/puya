import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, IndexExpression, NewArray, UInt64Constant
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb._utils import constant_bool_and_error
from puya.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder
from puya.awst_build.eb.arc4._utils import no_literal_items
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, StaticSizedCollectionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

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
        arg_kinds: list[mypy.nodes.ArgKind],
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
        no_literal_items(typ, location)
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        no_literal_items(typ, location)
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
        item_type = self.pytype.items
        return [
            builder_for_instance(
                item_type,
                IndexExpression(
                    base=base,
                    index=UInt64Constant(value=idx, source_location=self.source_location),
                    wtype=item_type.wtype,
                    source_location=self.source_location,
                ),
            )
            for idx in range(self._size)
        ]
