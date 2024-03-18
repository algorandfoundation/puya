from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, Literal, ReinterpretCast
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.arrays import DynamicArrayExpressionBuilder, dynamic_array_constructor
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, native_eb
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

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
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes()) as literal]:
                return var_expression(convert_arc4_literal(literal, self.produces(), location))
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                return var_expression(
                    ARC4Encode(value=eb.rvalue(), source_location=location, wtype=self.produces())
                )

        return dynamic_array_constructor(
            args=list(map(_coerce_to_byte, args)), wtype=self.produces(), location=location
        )


def _coerce_to_byte(arg: ExpressionBuilder | Literal) -> ExpressionBuilder:
    match arg:
        case Literal(value=int()) as literal:
            return var_expression(convert_arc4_literal(literal, wtypes.arc4_byte_type))
        case ExpressionBuilder(value_type=wtypes.ARC4UIntN(n=8) as wtype) as eb:
            if wtype != wtypes.arc4_byte_type:
                return var_expression(
                    ReinterpretCast(
                        expr=arg.rvalue(),
                        wtype=wtypes.arc4_byte_type,
                        source_location=arg.source_location,
                    )
                )
            return eb
        case _:
            raise CodeError("Expected a Byte, UInt64 or int type", arg.source_location)


class DynamicBytesExpressionBuilder(DynamicArrayExpressionBuilder):
    wtype = wtypes.arc4_dynamic_bytes

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "native":
                return native_eb(self.expr, location)
            case _:
                return super().member_access(name, location)
