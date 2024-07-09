import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Decode, ARC4Encode, Expression, TupleItemExpression
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_bytes, constant_bool_and_error, dummy_value
from puya.awst_build.eb.arc4._base import ARC4TypeBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4TupleGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_raise)
        match arg:
            case InstanceBuilder(
                pytype=pytypes.TupleType(items=items, generic=pytypes.GenericTupleType)
            ):
                typ = pytypes.GenericARC4TupleType.parameterise(items, location)
                wtype = typ.wtype
                assert isinstance(wtype, wtypes.ARC4Tuple)
                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=arg.resolve(), wtype=wtype, source_location=location), typ
                )
            case _:
                # don't know expected type
                raise CodeError("unexpected argument type", arg.source_location)


class ARC4TupleTypeBuilder(ARC4TypeBuilder[pytypes.TupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericARC4TupleType
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
        native_type = pytypes.GenericTupleType.parameterise(typ.items, location)
        arg = expect.exactly_one_arg_of_type_else_dummy(args, native_type, location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4Tuple)
        return ARC4TupleExpressionBuilder(
            ARC4Encode(value=arg.resolve(), wtype=wtype, source_location=location), typ
        )


class ARC4TupleExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.TupleType], StaticSizedCollectionBuilder
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericARC4TupleType
        super().__init__(typ, expr)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        match index:
            case LiteralBuilder(value=int(index_value)):
                pass
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                raise CodeError("tuple index must be a simple int literal", index.source_location)
            case _:
                raise CodeError("unexpected argument type", index.source_location)
        try:
            item_typ = self.pytype.items[index_value]
        except IndexError:
            raise CodeError("index out of bounds", index.source_location) from None
        return builder_for_instance(
            item_typ,
            TupleItemExpression(
                base=self.resolve(),
                index=index_value,
                source_location=location,
            ),
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                native_pytype = pytypes.GenericTupleType.parameterise(self.pytype.items, location)
                result_expr: Expression = ARC4Decode(
                    value=self.resolve(),
                    wtype=native_pytype.wtype,
                    source_location=location,
                )
                return TupleExpressionBuilder(result_expr, native_pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        logger.error(
            "item containment with ARC4 tuples is currently unsupported", location=location
        )
        return dummy_value(pytypes.BoolType, location)

    @typing.override
    def iterate(self) -> typing.Never:
        # could only support for homogenous types anyway, in which case use a StaticArray?
        raise CodeError("iterating ARC4 tuples is currently unsupported", self.source_location)

    @typing.override
    def iterate_static(self) -> Sequence[InstanceBuilder]:
        base = self.single_eval().resolve()
        return [
            builder_for_instance(
                item_type,
                TupleItemExpression(base=base, index=idx, source_location=self.source_location),
            )
            for idx, item_type in enumerate(self.pytype.items)
        ]

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing ARC4 tuples is currently unsupported", location)
