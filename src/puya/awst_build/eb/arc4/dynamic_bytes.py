from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, Literal, ReinterpretCast
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.arrays import (
    DynamicArrayClassExpressionBuilder,
    DynamicArrayExpressionBuilder,
)
from puya.awst_build.eb.arc4.base import native_eb
from puya.awst_build.eb.base import ExpressionBuilder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


class DynamicBytesClassExpressionBuilder(DynamicArrayClassExpressionBuilder):
    wtype: wtypes.ARC4DynamicArray

    def __init__(self, location: SourceLocation):
        super().__init__(location=location, wtype=wtypes.arc4_dynamic_bytes)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes()) as literal]:
                return DynamicBytesExpressionBuilder(
                    convert_arc4_literal(literal, self.wtype, location)
                )
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                return DynamicBytesExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), source_location=location, wtype=self.produces())
                )

        return super().call(
            args=list(map(_coerce_to_byte, args)),
            arg_kinds=arg_kinds,
            arg_names=arg_names,
            location=location,
        )


def _coerce_to_byte(arg: ExpressionBuilder | Literal) -> ExpressionBuilder:
    from puya.awst_build.eb.arc4 import UIntNExpressionBuilder

    match arg:
        case Literal(value=int()) as literal:
            return UIntNExpressionBuilder(convert_arc4_literal(literal, wtypes.arc4_byte_type))
        case ExpressionBuilder(value_type=wtypes.ARC4UIntN(n=8) as wtype) as eb:
            if wtype != wtypes.arc4_byte_type:
                return UIntNExpressionBuilder(
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
