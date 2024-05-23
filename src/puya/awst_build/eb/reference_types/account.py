from __future__ import annotations

import typing

from immutabledict import immutabledict

from puya import log
from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    BytesComparisonExpression,
    CheckedMaybe,
    EqualityComparison,
    Expression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    SingleEvaluation,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.reference_types.base import ReferenceValueExpressionBuilder
from puya.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


logger = log.get_logger(__name__)


class AccountClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(wtypes.account_wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                value: Expression = intrinsic_factory.zero_address(location)
            case [Literal(value=str(addr_value))]:
                if not wtypes.valid_address(addr_value):
                    raise CodeError(
                        f"Invalid address value. Address literals should be"
                        f" {ENCODED_ADDRESS_LENGTH} characters and not include base32 padding",
                        location,
                    )
                value = AddressConstant(value=addr_value, source_location=location)
            case [ExpressionBuilder() as eb]:
                value = expect_operand_wtype(eb, wtypes.bytes_wtype)
                address_bytes_temp = SingleEvaluation(value)
                is_correct_length = NumericComparisonExpression(
                    operator=NumericComparison.eq,
                    source_location=location,
                    lhs=UInt64Constant(value=32, source_location=location),
                    rhs=intrinsic_factory.bytes_len(address_bytes_temp, location),
                )
                address_bytes = CheckedMaybe.from_tuple_items(
                    expr=address_bytes_temp,
                    check=is_correct_length,
                    source_location=location,
                    comment="Address length is 32 bytes",
                )
                value = ReinterpretCast(
                    expr=address_bytes, wtype=wtypes.account_wtype, source_location=location
                )
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                value = intrinsic_factory.zero_address(location)
        return AccountExpressionBuilder(value)


class AccountOptedInExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder(value_type=wtypes.asset_wtype) as asset]:
                return BoolExpressionBuilder(
                    TupleItemExpression(
                        base=IntrinsicCall(
                            op_code="asset_holding_get",
                            immediates=["AssetBalance"],
                            stack_args=[self.expr, asset.rvalue()],
                            wtype=wtypes.WTuple(
                                (wtypes.uint64_wtype, wtypes.bool_wtype), location
                            ),
                            source_location=location,
                        ),
                        index=1,
                        source_location=location,
                    )
                )
            case [ExpressionBuilder(value_type=wtypes.application_wtype) as app]:
                return BoolExpressionBuilder(
                    IntrinsicCall(
                        op_code="app_opted_in",
                        stack_args=[self.expr, app.rvalue()],
                        source_location=location,
                        wtype=wtypes.bool_wtype,
                    )
                )
        raise CodeError("Unexpected argument", location)


class AccountExpressionBuilder(ReferenceValueExpressionBuilder):
    wtype = wtypes.account_wtype
    native_type = pytypes.BytesType
    native_access_member = "bytes"
    field_mapping = immutabledict(
        {
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
    )
    field_op_code = "acct_params_get"
    field_bool_comment = "account funded"

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name == "is_opted_in":
            return AccountOptedInExpressionBuilder(self.expr, location)
        return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        cmp_with_zero_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison.eq if negate else EqualityComparison.ne,
            rhs=intrinsic_factory.zero_address(location),
        )

        return BoolExpressionBuilder(cmp_with_zero_expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if not (
            other_expr.wtype == self.wtype  # can only compare with other Accounts?
            and op in (BuilderComparisonOp.eq, BuilderComparisonOp.ne)
        ):
            return NotImplemented
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other_expr,
        )
        return BoolExpressionBuilder(cmp_expr)
