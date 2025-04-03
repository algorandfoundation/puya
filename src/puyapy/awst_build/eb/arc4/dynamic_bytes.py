import typing
from collections.abc import Sequence

from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    BytesConstant,
    BytesEncoding,
    Expression,
    NewArray,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.arc4.dynamic_array import DynamicArrayExpressionBuilder
from puyapy.awst_build.eb.arc4.uint import UIntNTypeBuilder
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder

logger = log.get_logger(__name__)


class DynamicBytesTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4DynamicBytesType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case bytes(bytes_literal):
                if len(bytes_literal) > (algo_constants.MAX_BYTES_LENGTH - 2):
                    logger.error(
                        "encoded bytes exceed max length", location=literal.source_location
                    )

                bytes_expr = BytesConstant(
                    value=bytes_literal, encoding=BytesEncoding.unknown, source_location=location
                )
                return self._from_bytes_expr(bytes_expr, location)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder(pytype=pytypes.BytesLiteralType) as lit]:
                return lit.resolve_literal(DynamicBytesTypeBuilder(location))
            case []:
                bytes_expr: Expression = BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                )
            case [
                InstanceBuilder(pytype=single_arg_pytype) as eb
            ] if pytypes.BytesType <= single_arg_pytype:
                bytes_expr = eb.resolve()
            case _:
                non_literal_args = tuple(_coerce_to_byte(a).resolve() for a in args)
                return DynamicBytesExpressionBuilder(
                    NewArray(
                        values=non_literal_args, wtype=self._arc4_type, source_location=location
                    )
                )
        return self._from_bytes_expr(bytes_expr, location)

    @property
    def _arc4_type(self) -> wtypes.ARC4DynamicArray:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        return wtype

    def _from_bytes_expr(self, expr: Expression, location: SourceLocation) -> InstanceBuilder:
        encode_expr = ARC4Encode(value=expr, wtype=self._arc4_type, source_location=location)
        return DynamicBytesExpressionBuilder(encode_expr)


def _coerce_to_byte(builder: NodeBuilder) -> InstanceBuilder:
    arg = expect.instance_builder(
        builder, default=expect.default_dummy_value(pytypes.ARC4ByteType)
    )
    arg = arg.resolve_literal(UIntNTypeBuilder(pytypes.ARC4ByteType, arg.source_location))
    match arg:
        # can't use expect.argument_of_type here, we need a match statement
        case InstanceBuilder(pytype=pytypes.ARC4UIntNType(bits=8)):
            return arg
        case _:
            logger.error("invalid argument type", location=arg.source_location)
            return dummy_value(pytypes.ARC4ByteType, arg.source_location)


class DynamicBytesExpressionBuilder(DynamicArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(expr, pytypes.ARC4DynamicBytesType)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return BytesExpressionBuilder(
                    ARC4Decode(
                        value=self.resolve(), wtype=wtypes.bytes_wtype, source_location=location
                    )
                )
            case _:
                return super().member_access(name, location)
