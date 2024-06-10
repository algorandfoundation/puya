from __future__ import annotations

import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    BytesConstant,
    BytesEncoding,
    Expression,
    NewArray,
)
from puya.awst_build import pytypes
from puya.awst_build.arc4_utils import arc4_decode
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb.arc4.arrays import DynamicArrayExpressionBuilder
from puya.awst_build.eb.arc4.uint import UIntNTypeBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from puya.parse import SourceLocation


class DynamicBytesTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType], LiteralConverter):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4DynamicBytesType, location)

    @typing.override
    @property
    def convertable_literal_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.StrLiteralType,)

    @typing.override
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        return self.call([literal], [mypy.nodes.ARG_POS], [None], location)  # TODO: fixme

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        match args:
            case []:
                bytes_expr: Expression = BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                )
            case [LiteralBuilder(value=bytes(bytes_literal))]:
                bytes_expr = BytesConstant(
                    value=bytes_literal, encoding=BytesEncoding.unknown, source_location=location
                )
            case [InstanceBuilder(pytype=pytypes.BytesType) as eb]:
                bytes_expr = eb.resolve()
            case _:
                non_literal_args = tuple(_coerce_to_byte(a) for a in args)
                return DynamicBytesExpressionBuilder(
                    NewArray(values=non_literal_args, wtype=wtype, source_location=location)
                )
        encode_expr = ARC4Encode(value=bytes_expr, wtype=wtype, source_location=location)
        return DynamicBytesExpressionBuilder(encode_expr)


def _coerce_to_byte(arg: NodeBuilder) -> Expression:
    arg = require_instance_builder(arg)
    arg = arg.resolve_literal(UIntNTypeBuilder(pytypes.ARC4ByteType, arg.source_location))
    match arg:
        case InstanceBuilder(pytype=pytypes.ARC4UIntNType(bits=8)):
            return arg.resolve()
        # case InstanceBuilder(pytype=pytypes.ARC4UIntNType(bits=8)):
        #     return ReinterpretCast(
        #         expr=arg.resolve(),
        #         wtype=wtypes.arc4_byte_alias,
        #         source_location=arg.source_location,
        #     )
        case _:
            raise CodeError("invalid argument type", arg.source_location)


class DynamicBytesExpressionBuilder(DynamicArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(expr, pytypes.ARC4DynamicBytesType)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return BytesExpressionBuilder(
                    arc4_decode(self.resolve(), wtypes.bytes_wtype, location)
                )
            case _:
                return super().member_access(name, location)
