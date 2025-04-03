import typing
from collections.abc import Sequence

from puya import log, utils
from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    CheckedMaybe,
    Expression,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    UInt64Constant,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import compare_expr_bytes
from puyapy.awst_build.eb.arc4.static_array import StaticArrayExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.reference_types.account import AccountExpressionBuilder

logger = log.get_logger(__name__)


class AddressTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4AddressType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(str_value):
                if not utils.valid_address(str_value):
                    logger.error(
                        f"Invalid address value. Address literals should be"
                        f" {ENCODED_ADDRESS_LENGTH} characters and not include base32 padding",
                        location=literal.source_location,
                    )
                expr = AddressConstant(
                    value=str_value,
                    wtype=wtypes.arc4_address_alias,
                    source_location=location,
                )
                return AddressExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        if arg is None:
            result = _zero_address(location)
        elif arg.pytype == pytypes.StrLiteralType:
            return arg.resolve_literal(converter=AddressTypeBuilder(location))
        elif arg.pytype == pytypes.AccountType:  # Account is a final type
            result = _address_from_native(arg)
        else:
            arg = expect.argument_of_type_else_dummy(arg, pytypes.BytesType)
            arg = arg.single_eval()
            is_correct_length = NumericComparisonExpression(
                operator=NumericComparison.eq,
                source_location=location,
                lhs=UInt64Constant(value=32, source_location=location),
                rhs=intrinsic_factory.bytes_len(arg.resolve(), location),
            )
            result = CheckedMaybe.from_tuple_items(
                expr=_address_from_native(arg),
                check=is_correct_length,
                source_location=location,
                comment="Address length is 32 bytes",
            )
        return AddressExpressionBuilder(result)


class AddressExpressionBuilder(StaticArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(expr, pytypes.ARC4AddressType)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return compare_expr_bytes(
            lhs=self.resolve(),
            op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
            rhs=_zero_address(location),
            source_location=location,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if other.pytype == pytypes.StrLiteralType:
            rhs = other.resolve_literal(AddressTypeBuilder(other.source_location)).resolve()
        elif other.pytype == pytypes.AccountType:  # Account is a final type
            rhs = _address_from_native(other)
        elif pytypes.ARC4AddressType <= other.pytype:
            rhs = other.resolve()
        else:
            return NotImplemented
        return compare_expr_bytes(lhs=self.resolve(), op=op, rhs=rhs, source_location=location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return AccountExpressionBuilder(_address_to_native(self))
            case _:
                return super().member_access(name, location)


def _zero_address(location: SourceLocation) -> Expression:
    return intrinsic_factory.zero_address(location, as_type=wtypes.arc4_address_alias)


def _address_to_native(builder: InstanceBuilder) -> Expression:
    assert pytypes.ARC4AddressType <= builder.pytype
    return ReinterpretCast(
        expr=builder.resolve(),
        wtype=wtypes.account_wtype,
        source_location=builder.source_location,
    )


def _address_from_native(builder: InstanceBuilder) -> Expression:
    assert builder.pytype.is_type_or_subtype(pytypes.AccountType, pytypes.BytesType)
    return ReinterpretCast(
        expr=builder.resolve(),
        wtype=wtypes.arc4_address_alias,
        source_location=builder.source_location,
    )
