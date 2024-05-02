from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, BoolConstant, Expression, Literal
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.eb.base import (
        ExpressionBuilder,
    )
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4BoolClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def produces(self) -> wtypes.ARC4Type:
        return wtypes.arc4_bool_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                native_bool: Expression = BoolConstant(value=False, source_location=location)
            case [val]:
                native_bool = expect_operand_wtype(val, wtypes.bool_wtype)
            case _:
                raise CodeError(
                    f"arc4.Bool expects exactly one parameter of type {wtypes.bool_wtype}"
                )
        return ARC4BoolExpressionBuilder(
            ARC4Encode(
                value=native_bool,
                source_location=location,
                wtype=self.produces(),
            )
        )


class ARC4BoolExpressionBuilder(ARC4EncodedExpressionBuilder):
    wtype = wtypes.arc4_bool_wtype

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(self.expr, false_bytes=b"\x00", location=location, negate=negate)
