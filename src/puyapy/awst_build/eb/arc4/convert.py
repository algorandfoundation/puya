import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Encode, ARC4FromBytes, Expression, ReinterpretCast
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder

__all__ = [
    "DecodeBuilder",
    "EncodeBuilder",
]

logger = log.get_logger(__name__)


class EncodeBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_raise)
        if isinstance(arg.pytype.wtype, wtypes.ARC4Type):
            # use ReinterpretCast(.) instead of ARC4Encode(.) to avoid
            # triggering the arc4 copy validator for already encoded values
            result_expr: Expression = ReinterpretCast(
                expr=arg.resolve(),
                wtype=wtypes.bytes_wtype,
                source_location=location,
            )
        else:
            result_expr = ARC4Encode(
                value=arg.resolve(),
                source_location=location,
            )
        return BytesExpressionBuilder(result_expr)


class DecodeBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [
                NodeBuilder(pytype=pytypes.TypeType(typ=target_type)),
                second,
            ]:
                validate = True
            case [
                NodeBuilder(pytype=pytypes.TypeType(typ=target_type)),
                second,
                LiteralBuilder(value=bool(validate)),
            ]:
                pass
            case _:
                logger.error(
                    "expected an ARC-4 encodable type and a Bytes argument",
                    location=location,
                )
                return dummy_value(pytypes.BytesType, location)
        bytes_arg = expect.argument_of_type_else_dummy(
            second, pytypes.BytesType, resolve_literal=True
        )
        result_expr = ARC4FromBytes(
            value=bytes_arg.resolve(),
            wtype=target_type.checked_wtype(location),
            validate=validate,
            source_location=location,
        )
        return builder_for_instance(target_type, result_expr)
