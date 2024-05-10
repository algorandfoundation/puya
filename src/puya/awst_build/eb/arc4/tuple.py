from __future__ import annotations

import typing

from puya import arc4_util, log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, Expression, Literal, TupleItemExpression
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, ARC4EncodedExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder, GenericClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4TupleGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder(value_type=wtypes.WTuple(types=item_types)) as eb]:
                wtype = arc4_util.make_tuple_wtype(item_types, location)
                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), wtype=wtype, source_location=location)
                )
        raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleClassExpressionBuilder(ARC4ClassExpressionBuilder[wtypes.ARC4Tuple]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericARC4TupleType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4Tuple)
        super().__init__(wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:

        match args:
            case [ExpressionBuilder(value_type=wtypes.WTuple() as tuple_wtype) as eb]:
                wtype = self.produces()
                if wtype.types != tuple_wtype.types:
                    expected_type = wtypes.WTuple(wtype.types, location)
                    raise CodeError(
                        f"Invalid arg type: expected {expected_type}, got {tuple_wtype}",
                        location,
                    )
                return ARC4TupleExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), wtype=wtype, source_location=location)
                )

        raise CodeError("Invalid/unhandled arguments", location)


class ARC4TupleExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        self.pytyp = typ
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
