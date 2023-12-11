from __future__ import annotations

import typing

from immutabledict import immutabledict

from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    BytesComparisonExpression,
    EqualityComparison,
    IntrinsicCall,
    Literal,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.reference_types.base import ReferenceValueExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    import mypy.nodes

    from puya.parse import SourceLocation


class AccountClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.account_wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(addr_value), source_location=loc)]:
                if not wtypes.valid_address(addr_value):
                    raise CodeError(
                        f"Invalid address value. Address literals should be "
                        f"{ENCODED_ADDRESS_LENGTH} characters and not include base32 "
                        " padding",
                        location,
                    )
                # TODO: replace loc with location
                const = AddressConstant(value=addr_value, source_location=loc)
                return var_expression(const)
            case [ExpressionBuilder() as eb]:
                account_expr = expect_operand_wtype(eb, wtypes.account_wtype)
                return AccountExpressionBuilder(account_expr)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AccountExpressionBuilder(ReferenceValueExpressionBuilder):
    wtype = wtypes.account_wtype
    native_wtype = wtypes.bytes_wtype
    native_access_member = "bytes"
    field_mapping = immutabledict(
        {
            "balance": ("AcctBalance", wtypes.uint64_wtype),
            "min_balance": ("AcctMinBalance", wtypes.uint64_wtype),
            "auth_address": ("AcctAuthAddr", wtypes.account_wtype),
            "total_num_uint": ("AcctTotalNumUint", wtypes.uint64_wtype),
            "total_num_byte_slice": ("AcctTotalNumByteSlice", wtypes.uint64_wtype),
            "total_extra_app_pages": ("AcctTotalExtraAppPages", wtypes.uint64_wtype),
            "total_apps_created": ("AcctTotalAppsCreated", wtypes.uint64_wtype),
            "total_apps_opted_in": ("AcctTotalAppsOptedIn", wtypes.uint64_wtype),
            "total_assets_created": ("AcctTotalAssetsCreated", wtypes.uint64_wtype),
            "total_assets": ("AcctTotalAssets", wtypes.uint64_wtype),
            "total_boxes": ("AcctTotalBoxes", wtypes.uint64_wtype),
            "total_box_bytes": ("AcctTotalBoxBytes", wtypes.uint64_wtype),
        }
    )
    field_op_code = "acct_params_get"
    field_bool_comment = "account funded"

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        cmp_with_zero_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison.eq if negate else EqualityComparison.ne,
            rhs=IntrinsicCall(
                source_location=location,
                wtype=self.wtype,
                op_code="global",
                immediates=["ZeroAddress"],
            ),
        )

        return var_expression(cmp_with_zero_expr)

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
        return var_expression(cmp_expr)
