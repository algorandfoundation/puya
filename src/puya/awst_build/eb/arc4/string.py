from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    BytesConstant,
    BytesEncoding,
    Literal,
)
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, ARC4EncodedExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.eb.base import ExpressionBuilder
    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class StringClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.arc4_string_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(str_val), source_location=loc)]:
                return var_expression(
                    ARC4Encode(
                        value=BytesConstant(
                            value=str_val.encode("utf8"),
                            source_location=loc,
                            encoding=BytesEncoding.utf8,
                        ),
                        source_location=location,
                        wtype=self.produces(),
                    )
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class StringExpressionBuilder(ARC4EncodedExpressionBuilder):
    wtype = wtypes.arc4_string_wtype
