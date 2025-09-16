import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayReplace,
    ConvertArray,
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
from puyapy.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance, builder_for_type
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
    "ImmutableFixedArrayGenericTypeBuilder",
    "ImmutableFixedArrayTypeBuilder",
    "ImmutableFixedArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class _FixedArrayGenericTypeBuilder(GenericTypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        super().__init__(location)
        self._typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if not isinstance(arg, StaticSizedCollectionBuilder):
            raise CodeError("requires a statically sized argument", location)
        arg_item_type = arg.iterable_item_type()
        size_type = pytypes.TypingLiteralType(
            value=len(arg.iterate_static()), source_location=location
        )
        arr_typ = self._typ.parameterise([arg_item_type, size_type], location)
        typ_builder = builder_for_type(arr_typ, location)
        return typ_builder.call(args, arg_kinds, arg_names, location)


class FixedArrayGenericTypeBuilder(_FixedArrayGenericTypeBuilder):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(pytypes.GenericFixedArrayType, location)


class ImmutableFixedArrayGenericTypeBuilder(_FixedArrayGenericTypeBuilder):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(pytypes.GenericImmutableFixedArrayType, location)


class _FixedArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(
        self, *, typ: pytypes.PyType, generic_typ: pytypes.PyType, location: SourceLocation
    ):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == generic_typ
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
        elif isinstance(
            arg.pytype.wtype,
            wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray,
        ):
            new_array = ConvertArray(expr=arg.resolve(), wtype=wtype, source_location=location)
        elif isinstance(arg, StaticSizedCollectionBuilder):
            item_builders = arg.iterate_static()
            if len(item_builders) != self._size:
                logger.error("argument has incorrect length", location=arg.source_location)
            items = [ib.resolve() for ib in item_builders]
            new_array = NewArray(values=items, wtype=wtype, source_location=location)
        else:
            logger.error("unsupported collection type", location=arg.source_location)
            return dummy_value(typ, location)
        return builder_for_instance(typ, new_array)


class FixedArrayTypeBuilder(_FixedArrayTypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(
            typ=typ,
            generic_typ=pytypes.GenericFixedArrayType,
            location=location,
        )


class ImmutableFixedArrayTypeBuilder(_FixedArrayTypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(
            typ=typ,
            generic_typ=pytypes.GenericImmutableFixedArrayType,
            location=location,
        )


class _FixedArrayExpressionBuilder(_ArrayExpressionBuilder, StaticSizedCollectionBuilder):
    def __init__(self, *, expr: Expression, typ: pytypes.PyType, generic_typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        assert (
            typ.generic == generic_typ
        ), f"{typ=!s}, {typ.generic=!s}, {generic_typ=!s}, {type(self).__name__=!s}"
        size = typ.size
        assert size is not None
        self._size = size
        super().__init__(expr, typ)

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

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "replace":
                return _Replace(self.resolve(), self.pytype, location)
            case "freeze":
                return _Freeze(self.resolve(), self.pytype, location)
            case _:
                return super().member_access(name, location)


class FixedArrayExpressionBuilder(_FixedArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        super().__init__(expr=expr, typ=typ, generic_typ=pytypes.GenericFixedArrayType)


class ImmutableFixedArrayExpressionBuilder(_FixedArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        super().__init__(expr=expr, typ=typ, generic_typ=pytypes.GenericImmutableFixedArrayType)


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


class _ArrayFunc(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ


class _Replace(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if expect.exactly_n_args(args, location, 2):
            index = expect.argument_of_type_else_dummy(
                args[0], pytypes.UInt64Type, resolve_literal=True
            )
            value = expect.argument_of_type_else_dummy(args[1], self.typ.items)
        else:
            index = dummy_value(pytypes.UInt64Type, location)
            value = dummy_value(self.typ.items, location)
        return builder_for_instance(
            self.typ,
            ArrayReplace(
                base=self.expr,
                index=index.resolve(),
                value=value.resolve(),
                source_location=location,
            ),
        )


class _Freeze(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        imm_typ = pytypes.GenericImmutableFixedArrayType.parameterise(
            [
                self.typ.items,
                pytypes.TypingLiteralType(value=self.typ.size, source_location=location),
            ],
            location,
        )
        wtype = imm_typ.checked_wtype(location)
        assert isinstance(wtype, wtypes.ARC4StaticArray), wtype
        result_expr = ConvertArray(expr=self.expr, wtype=wtype, source_location=location)
        return builder_for_instance(imm_typ, result_expr)
