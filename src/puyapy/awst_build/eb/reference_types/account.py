import typing
from collections.abc import Sequence

from puya import log, utils
from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    TupleItemExpression,
    UInt64Constant,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import (
    cast_to_bytes,
    compare_bytes,
    compare_expr_bytes,
    dummy_value,
)
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.reference_types._base import ReferenceValueExpressionBuilder

logger = log.get_logger(__name__)


class AccountTypeBuilder(BytesBackedTypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.AccountType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(str_value):
                if not utils.valid_address(str_value):
                    logger.error(
                        "invalid address value - should have length"
                        f" {ENCODED_ADDRESS_LENGTH} and not include base32 padding",
                        location=literal.source_location,
                    )
                expr = AddressConstant(
                    value=str_value,
                    wtype=wtypes.account_wtype,
                    source_location=location,
                )
                return AccountExpressionBuilder(expr)
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
        match arg:
            case InstanceBuilder(pytype=pytypes.StrLiteralType):
                return arg.resolve_literal(converter=AccountTypeBuilder(location))
            case None:
                value: Expression = intrinsic_factory.zero_address(location)
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.BytesType)
                address_bytes_temp = arg.single_eval().resolve()
                is_correct_length = NumericComparisonExpression(
                    operator=NumericComparison.eq,
                    source_location=location,
                    lhs=UInt64Constant(value=32, source_location=location),
                    rhs=intrinsic_factory.bytes_len(address_bytes_temp, location),
                )
                value = CheckedMaybe.from_tuple_items(
                    expr=ReinterpretCast(
                        expr=address_bytes_temp,
                        wtype=wtypes.account_wtype,
                        source_location=location,
                    ),
                    check=is_correct_length,
                    source_location=location,
                    comment="Address length is 32 bytes",
                )
        return AccountExpressionBuilder(value)


class AccountExpressionBuilder(ReferenceValueExpressionBuilder):
    def __init__(self, expr: Expression):
        native_type = pytypes.BytesType
        native_access_member = "bytes"
        field_mapping = {
            "balance": ("AcctBalance", pytypes.UInt64Type),
            "min_balance": ("AcctMinBalance", pytypes.UInt64Type),
            "auth_address": ("AcctAuthAddr", pytypes.AccountType),
            "total_num_uint": ("AcctTotalNumUint", pytypes.UInt64Type),
            "total_num_byte_slice": ("AcctTotalNumByteSlice", pytypes.UInt64Type),
            "total_extra_app_pages": ("AcctTotalExtraAppPages", pytypes.UInt64Type),
            "total_apps_created": ("AcctTotalAppsCreated", pytypes.UInt64Type),
            "total_apps_opted_in": ("AcctTotalAppsOptedIn", pytypes.UInt64Type),
            "total_assets_created": ("AcctTotalAssetsCreated", pytypes.UInt64Type),
            "total_assets": ("AcctTotalAssets", pytypes.UInt64Type),
            "total_boxes": ("AcctTotalBoxes", pytypes.UInt64Type),
            "total_box_bytes": ("AcctTotalBoxBytes", pytypes.UInt64Type),
        }
        field_op_code = "acct_params_get"
        field_bool_comment = "account funded"
        super().__init__(
            expr,
            typ=pytypes.AccountType,
            native_type=native_type,
            native_access_member=native_access_member,
            field_mapping=field_mapping,
            field_op_code=field_op_code,
            field_bool_comment=field_bool_comment,
        )

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return cast_to_bytes(self.resolve(), location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "is_opted_in":
            return _IsOptedIn(self.resolve(), location)
        return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return compare_expr_bytes(
            lhs=self.resolve(),
            op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
            rhs=intrinsic_factory.zero_address(location),
            source_location=location,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(converter=AccountTypeBuilder(other.source_location))
        return compare_bytes(self=self, op=op, other=other, source_location=location)


class _IsOptedIn(FunctionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is None:
            return dummy_value(pytypes.BoolType, location)
        elif pytypes.AssetType <= arg.pytype:
            return BoolExpressionBuilder(
                TupleItemExpression(
                    base=IntrinsicCall(
                        op_code="asset_holding_get",
                        immediates=["AssetBalance"],
                        stack_args=[self.expr, arg.resolve()],
                        wtype=wtypes.WTuple(
                            types=(wtypes.uint64_wtype, wtypes.bool_wtype),
                            source_location=location,
                        ),
                        source_location=location,
                    ),
                    index=1,
                    source_location=location,
                )
            )
        else:
            arg = expect.argument_of_type_else_dummy(arg, pytypes.ApplicationType)
            return BoolExpressionBuilder(
                IntrinsicCall(
                    op_code="app_opted_in",
                    stack_args=[self.expr, arg.resolve()],
                    source_location=location,
                    wtype=wtypes.bool_wtype,
                )
            )
