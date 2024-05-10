from __future__ import annotations

import typing

from puya import arc4_util, log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Expression,
    Literal,
    TupleItemExpression,
)
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, ARC4EncodedExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build import pytypes
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4TupleClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.ARC4Tuple | None = None):
        super().__init__(location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        if not self.wtype:
            raise CodeError(
                "Unparameterized arc4.Tuple class cannot be used as a type", self.source_location
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
        tuple_item_types = list[wtypes.ARC4Type]()
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
        self.wtype = wtypes.ARC4Tuple(tuple_item_types, location)
        return self

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        wtype = self.wtype
        match args:
            case [ExpressionBuilder(value_type=wtypes.WTuple() as tuple_wtype) as eb]:
                tuple_ex = eb.rvalue()

                if wtype is None:
                    wtype = arc4_util.make_tuple_wtype(tuple_wtype.types, location)
                else:
                    expected_type = wtypes.WTuple(wtype.types, location)
                    if tuple_ex.wtype != expected_type:
                        raise CodeError(
                            f"Invalid arg type: expected {expected_type}, got {tuple_ex.wtype}",
                            location,
                        )

                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=tuple_ex, wtype=wtype, source_location=location)
                )

        raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4Tuple)
        self.wtype: wtypes.ARC4Tuple = expr.wtype
        super().__init__(expr)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        index_expr_or_literal = index
        match index_expr_or_literal:
            case Literal(value=int(index_value)) as index_literal:
                try:
                    self.wtype.types[index_value]
                except IndexError as ex:
                    raise CodeError(
                        "Tuple index out of bounds", index_literal.source_location
                    ) from ex
                # TODO: use pytype
                return var_expression(
                    TupleItemExpression(
                        base=self.expr,
                        index=index_value,
                        source_location=location,
                    )
                )
            case _:
                raise CodeError("arc4.Tuple can only be indexed by int constants")

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)
