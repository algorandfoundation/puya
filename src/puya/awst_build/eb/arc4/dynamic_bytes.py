from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, Expression, Literal, NewArray, ReinterpretCast
from puya.awst_build import pytypes
from puya.awst_build.arc4_utils import arc4_decode
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.arrays import DynamicArrayExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


class DynamicBytesClassExpressionBuilder(BytesBackedClassExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4DynamicBytesType, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        wtype = self.produces()
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        match args:
            case [Literal(value=bytes()) as literal]:
                return DynamicBytesExpressionBuilder(
                    convert_arc4_literal(literal, wtype, location)
                )
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                return DynamicBytesExpressionBuilder(
                    ARC4Encode(value=eb.rvalue(), source_location=location, wtype=wtype)
                )

        non_literal_args = tuple(_coerce_to_byte(a) for a in args)
        return DynamicBytesExpressionBuilder(
            NewArray(values=non_literal_args, wtype=wtype, source_location=location)
        )


def _coerce_to_byte(arg: ExpressionBuilder | Literal) -> Expression:
    match arg:
        case Literal(value=int()) as literal:
            return convert_arc4_literal(literal, wtypes.arc4_byte_type)
        case ExpressionBuilder(value_type=wtypes.ARC4UIntN(n=8) as wtype) as eb:
            if wtype != wtypes.arc4_byte_type:
                return ReinterpretCast(
                    expr=arg.rvalue(),
                    wtype=wtypes.arc4_byte_type,
                    source_location=arg.source_location,
                )
            return eb.rvalue()
        case _:
            raise CodeError("Expected a Byte, UInt64 or int type", arg.source_location)


class DynamicBytesExpressionBuilder(DynamicArrayExpressionBuilder):
    wtype = wtypes.arc4_dynamic_bytes

    def __init__(self, expr: Expression):
        super().__init__(expr, pytypes.ARC4DynamicBytesType)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "native":
                return BytesExpressionBuilder(arc4_decode(self.expr, wtypes.bytes_wtype, location))
            case _:
                return super().member_access(name, location)
