from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Decode, ARC4Encode, Expression, Literal, TupleItemExpression
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import bool_eval_to_constant, get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    arc4_compare_bytes,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    GenericTypeBuilder,
    InstanceBuilder,
    InstanceExpressionBuilder,
    Iteration,
    NodeBuilder,
)
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4TupleGenericClassExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case [NodeBuilder(pytype=pytypes.TupleType(items=items)) as eb]:
                typ = pytypes.GenericARC4TupleType.parameterise(items, location)
                wtype = typ.wtype
                assert isinstance(wtype, wtypes.ARC4Tuple)
                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), wtype=wtype, source_location=location), typ
                )
        raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleClassExpressionBuilder(ARC4ClassExpressionBuilder[pytypes.TupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericARC4TupleType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:

        match args:
            case [NodeBuilder(pytype=pytypes.TupleType() as tuple_type) as eb]:
                typ = self.produces()
                if typ.items != tuple_type.items:
                    expected_type = pytypes.GenericTupleType.parameterise(typ.items, location)
                    raise CodeError(
                        f"Invalid arg type: expected {expected_type}, got {tuple_type}",
                        location,
                    )
                wtype = typ.wtype
                assert isinstance(wtype, wtypes.ARC4Tuple)
                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), wtype=wtype, source_location=location),
                    self.produces(),
                )

        raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleExpressionBuilder(InstanceExpressionBuilder[pytypes.TupleType]):

    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        super().__init__(typ, expr)

    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        index_expr_or_literal = index
        match index_expr_or_literal:
            case Literal(value=int(index_value)) as index_literal:
                pass
            case _:
                raise CodeError("arc4.Tuple can only be indexed by int constants")
        try:
            item_typ = self.pytype.items[index_value]
        except IndexError as ex:
            raise CodeError("Tuple index out of bounds", index_literal.source_location) from ex
        return builder_for_instance(
            item_typ,
            TupleItemExpression(
                base=self.expr,
                index=index_value,
                source_location=location,
            ),
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "native":
                native_pytype = pytypes.GenericTupleType.parameterise(self.pytype.items, location)
                result_expr: Expression = ARC4Decode(
                    value=self.expr,
                    wtype=native_pytype.wtype,
                    source_location=location,
                )
                return TupleExpressionBuilder(result_expr, native_pytype)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        return arc4_compare_bytes(self, op, other, location)

    @typing.override
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        raise CodeError("item containment with ARC4 tuples is currently unsupported", location)

    @typing.override
    def iterate(self) -> Iteration:
        # could only support for homogenous types anyway, in which case use a StaticArray?
        raise CodeError("iterating ARC4 tuples is currently unsupported", self.source_location)

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        raise CodeError("slicing ARC4 tuples is currently unsupported", location)
