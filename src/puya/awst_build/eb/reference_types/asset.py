from __future__ import annotations

import typing
from typing import Sequence

from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.reference_types.base import UInt64BackedReferenceValueExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    import mypy.nodes

    from puya.parse import SourceLocation


class AssetClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.asset_wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                uint64_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
                return AssetExpressionBuilder(uint64_expr)
            case [Literal(value=int(int_value), source_location=loc)]:
                const = UInt64Constant(value=int_value, source_location=loc)
                return AssetExpressionBuilder(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


ASSET_HOLDING_FIELD_MAPPING: typing.Final = {
    "balance": ("AssetBalance", wtypes.uint64_wtype),
    "frozen": ("AssetFrozen", wtypes.bool_wtype),
}


class AssetHoldingExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, asset: Expression, holding_field: str, location: SourceLocation):
        self.asset = asset
        self.holding_field = holding_field
        super().__init__(location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                account_expr = expect_operand_wtype(eb, wtypes.account_wtype)
                immediate, wtype = ASSET_HOLDING_FIELD_MAPPING[self.holding_field]
                asset_params_get = IntrinsicCall(
                    source_location=location,
                    wtype=wtypes.WTuple.from_types((wtype, wtypes.bool_wtype)),
                    op_code="asset_holding_get",
                    immediates=[immediate],
                    stack_args=[account_expr, self.asset],
                )
                return var_expression(
                    CheckedMaybe(asset_params_get, comment="account opted into asset")
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AssetExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    wtype = wtypes.asset_wtype
    native_access_member = "asset_id"
    field_mapping = immutabledict(
        {
            "total": ("AssetTotal", wtypes.uint64_wtype),
            "decimals": ("AssetDecimals", wtypes.uint64_wtype),
            "default_frozen": ("AssetDefaultFrozen", wtypes.bool_wtype),
            "unit_name": ("AssetUnitName", wtypes.bytes_wtype),
            "name": ("AssetName", wtypes.bytes_wtype),
            "url": ("AssetURL", wtypes.bytes_wtype),
            "metadata_hash": ("AssetMetadataHash", wtypes.bytes_wtype),
            "manager": ("AssetManager", wtypes.account_wtype),
            "reserve": ("AssetReserve", wtypes.account_wtype),
            "freeze": ("AssetFreeze", wtypes.account_wtype),
            "clawback": ("AssetClawback", wtypes.account_wtype),
            "creator": ("AssetCreator", wtypes.account_wtype),
        }
    )
    field_op_code = "asset_params_get"
    field_bool_comment = "asset exists"

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name in ASSET_HOLDING_FIELD_MAPPING:
            return AssetHoldingExpressionBuilder(self.expr, name, location)
        return super().member_access(name, location)
