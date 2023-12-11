from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Expression,
    IndexExpression,
    Literal,
    TupleExpression,
    UInt64Constant,
)
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class ARC4TupleGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        tuple_item_types = list[wtypes.WType]()
        for index in indexes:
            match index:
                case TypeClassExpressionBuilder() as type_class:
                    wtype = type_class.produces()
                    if not wtypes.is_arc4_encoded_type(wtype):
                        raise CodeError(
                            "ARC4 Tuples can only contain ARC4 encoded values", location
                        )
                    tuple_item_types.append(wtype)
                case _:
                    raise CodeError("Invalid type parameter", index.source_location)
        return ARC4TupleClassExpressionBuilder(
            location, wtypes.ARC4Tuple.from_types(tuple_item_types)
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return tuple_constructor(args, None, location)


def tuple_constructor(
    args: Sequence[ExpressionBuilder | Literal],
    wtype: wtypes.ARC4Tuple | None,
    location: SourceLocation,
) -> ExpressionBuilder:
    match args:
        case [TupleExpressionBuilder() as teb]:
            tuple_ex = teb.rvalue()
            if not isinstance(tuple_ex, TupleExpression):
                raise CodeError("arc4.Tuple must be instantiated with a tuple", location)

            if wtype is None:
                wtype = wtypes.ARC4Tuple.from_types(tuple_ex.wtype.types)
            else:
                expected_type = wtypes.WTuple.from_types(wtype.types)
                if tuple_ex.wtype != expected_type:
                    raise CodeError(
                        f"Invalid arg type: expected {expected_type}, got {tuple_ex.wtype}",
                        location,
                    )

            return var_expression(
                ARC4Encode(value=tuple_ex, wtype=wtype, source_location=location)
            )

    raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.ARC4Tuple | None = None):
        super().__init__(location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        if not self.wtype:
            # TODO: make CodeError
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.wtype

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self.index_multiple((index,), location)

    def index_multiple(
        self,
        indexes: Sequence[ExpressionBuilder | Literal],
        location: SourceLocation,
    ) -> TypeClassExpressionBuilder:
        tuple_item_types = list[wtypes.WType]()
        for index in indexes:
            match index:
                case TypeClassExpressionBuilder() as type_class:
                    wtype = type_class.produces()
                    if not wtypes.is_arc4_encoded_type(wtype):
                        raise CodeError(
                            "ARC4 Tuples can only contain ARC4 encoded values", location
                        )
                    tuple_item_types.append(wtype)
                case _:
                    raise CodeError("Invalid type parameter", index.source_location)
        self.wtype = wtypes.ARC4Tuple.from_types(tuple_item_types)
        return self

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return tuple_constructor(args, self.wtype, location)


class ARC4TupleExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4Tuple)
        self.wtype: wtypes.ARC4Tuple = expr.wtype
        super().__init__(expr)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        match index:
            case Literal(value=int(index_int), source_location=index_loc):
                try:
                    item_wtype = self.wtype.types[index_int]
                except IndexError as ex:
                    raise CodeError("Tuple index out of bounds", index_loc) from ex
                return var_expression(
                    IndexExpression(
                        source_location=location,
                        base=self.expr,
                        index=UInt64Constant(value=index_int, source_location=index_loc),
                        wtype=item_wtype,
                    )
                )
            case _:
                raise CodeError(f"{self.wtype.name} can only be indexed with literal values")
