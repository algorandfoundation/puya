from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes
import structlog

from wyvern.algo_constants import ENCODED_ADDRESS_LENGTH
from wyvern.awst import wtypes
from wyvern.awst.nodes import (
    AddressConstant,
    BytesComparisonExpression,
    EqualityComparison,
    IntrinsicCall,
    Literal,
    ReinterpretCast,
)
from wyvern.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from wyvern.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.awst_build.utils import convert_literal_to_expr
from wyvern.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from wyvern.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class AddressClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.address_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(addr_value), source_location=loc)]:
                if not wtypes.valid_address(addr_value):
                    raise CodeError(
                        f"Invalid address value. Address literals should be "
                        f"{ENCODED_ADDRESS_LENGTH} characters and not include base32 "
                        " padding",
                        location,
                    )
                # TODO: replace loc with location
                const = AddressConstant(value=addr_value, source_location=loc)
                return var_expression(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AddressExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.address_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "bytes":
                return var_expression(
                    ReinterpretCast(
                        source_location=location, wtype=wtypes.bytes_wtype, expr=self.expr
                    )
                )
        return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        cmp_with_zero_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison.eq if negate else EqualityComparison.ne,
            rhs=IntrinsicCall(
                source_location=location,
                wtype=wtypes.address_wtype,
                op_code="global",
                immediates=["ZeroAddress"],
            ),
        )
        return var_expression(cmp_with_zero_expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp_expr)
