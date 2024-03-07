from __future__ import annotations

import typing
from typing import Sequence

from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, Literal, ReinterpretCast
from puya.awst_build.eb.arc4.arrays import DynamicArrayExpressionBuilder, dynamic_array_constructor
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, ARC4DecodeBuilder
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import convert_literal

if typing.TYPE_CHECKING:
    import mypy.nodes

    from puya.parse import SourceLocation


class DynamicBytesClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def produces(self) -> wtypes.ARC4DynamicArray:
        return wtypes.arc4_dynamic_bytes

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes()) as literal]:
                return var_expression(
                    convert_literal(literal, wtypes.arc4_dynamic_bytes, location)
                )
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                return var_expression(
                    ARC4Encode(
                        value=eb.rvalue(),
                        source_location=location,
                        wtype=wtypes.arc4_dynamic_bytes,
                    )
                )

        return dynamic_array_constructor(
            args=list(map(_coerce_to_byte, args)), wtype=self.produces(), location=location
        )


def _coerce_to_byte(arg: ExpressionBuilder | Literal) -> ExpressionBuilder | Literal:
    if isinstance(arg, Literal):
        return arg
    value_type = arg.value_type
    if (
        isinstance(value_type, wtypes.ARC4UIntN)
        and value_type.n == 8
        and value_type != wtypes.arc4_byte_type
    ):
        return var_expression(
            ReinterpretCast(
                expr=arg.rvalue(),
                wtype=wtypes.arc4_byte_type,
                source_location=arg.source_location,
            )
        )
    return arg


class DynamicBytesExpressionBuilder(DynamicArrayExpressionBuilder):
    wtype = wtypes.arc4_dynamic_bytes

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "decode":
                return ARC4DecodeBuilder(self.expr, location)
            case _:
                return super().member_access(name, location)
