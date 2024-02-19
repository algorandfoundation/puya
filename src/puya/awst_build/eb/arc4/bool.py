from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Literal,
)
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.eb.base import (
        ExpressionBuilder,
    )
    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class ARC4BoolClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.arc4_bool_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [val]:
                return var_expression(
                    ARC4Encode(
                        value=expect_operand_wtype(val, wtypes.bool_wtype),
                        source_location=location,
                        wtype=self.produces(),
                    )
                )
            case _:
                raise CodeError(
                    f"arc4.Bool expects exactly one parameter of type {wtypes.bool_wtype}"
                )


class ARC4BoolExpressionBuilder(ARC4EncodedExpressionBuilder):
    wtype = wtypes.arc4_bool_wtype

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(self.expr, false_bytes=b"\x00", location=location, negate=negate)
