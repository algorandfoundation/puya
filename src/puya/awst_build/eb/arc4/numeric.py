from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Expression,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build.eb._utils import uint64_to_biguint
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    arc4_bool_bytes,
    get_integer_literal_value,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError, TodoError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class NumericARC4ClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self.wtype: wtypes.ARC4UIntN | wtypes.ARC4UFixedNxM | None = None

    def produces(self) -> wtypes.WType:
        if self.wtype is None:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if not self.wtype:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with"
                " the generic type parameter."
            )
        match args:
            case [Literal() as lit]:
                return var_expression(convert_arc4_literal(lit, self.wtype, location))
            case [ExpressionBuilder(value_type=wtypes.WType() as value_type) as eb]:
                value = eb.rvalue()
                if value_type not in (
                    wtypes.bool_wtype,
                    wtypes.uint64_wtype,
                    wtypes.biguint_wtype,
                ):
                    raise CodeError(
                        f"{self.wtype} constructor expects an int literal or a "
                        "uint64 expression or a biguint expression"
                    )
                return var_expression(
                    ARC4Encode(value=value, source_location=location, wtype=self.wtype)
                )
            case _:
                raise CodeError(
                    "Invalid/unhandled arguments",
                    location,
                )


class ByteClassExpressionBuilder(NumericARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self.wtype = wtypes.arc4_byte_type


class UIntNClassExpressionBuilder(NumericARC4ClassExpressionBuilder):
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        n = get_integer_literal_value(index, "UIntN scale")
        if n % 8 or not (8 <= n <= 512):
            raise CodeError(
                "UIntN scale must be between 8 and 512 bits, and be a multiple of 8",
                location,
            )
        self.wtype = wtypes.ARC4UIntN.from_scale(n)
        return self


class UFixedNxMClassExpressionBuilder(NumericARC4ClassExpressionBuilder):
    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        try:
            scale_expr, precision_expr = index
        except ValueError as ex:
            raise CodeError(f"Expected two type arguments, got {len(index)}", location) from ex
        n = get_integer_literal_value(scale_expr, "UFixedNxM scale")
        m = get_integer_literal_value(precision_expr, "UFixedNxM precision")

        if n % 8 or not (8 <= n <= 512):
            raise CodeError(
                "UFixedNxM scale must be between 8 and 512 bits, and be a multiple of 8",
                location,
            )
        if not (1 <= m < 160):
            raise CodeError("UFixedNxM precision must be between 1 and 160.")
        self.wtype = wtypes.ARC4UFixedNxM.from_scale_and_precision(n=n, m=m)
        return self


class UIntNExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4UIntN)
        self.wtype: wtypes.ARC4UIntN = expr.wtype
        super().__init__(expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.wtype.n // 8),
            location=location,
            negate=negate,
        )

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(other, Literal):
            other_expr = convert_arc4_literal(other, self.wtype)
        else:
            other_expr = other.rvalue()
        match other_expr.wtype:
            case wtypes.biguint_wtype:
                pass
            case wtypes.ARC4UIntN():
                other_expr = ReinterpretCast(
                    expr=other_expr,
                    wtype=wtypes.biguint_wtype,
                    source_location=other_expr.source_location,
                )
            case wtypes.uint64_wtype:
                other_expr = uint64_to_biguint(other, location)
            case wtypes.bool_wtype:
                raise TodoError(location, "TODO: support upcast from bool to arc4.UIntN")
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=ReinterpretCast(
                expr=self.expr,
                wtype=wtypes.biguint_wtype,
                source_location=self.source_location,
            ),
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp_expr)


class UFixedNxMExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4UFixedNxM)
        self.wtype: wtypes.ARC4UFixedNxM = expr.wtype
        super().__init__(expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.wtype.n // 8),
            location=location,
            negate=negate,
        )
