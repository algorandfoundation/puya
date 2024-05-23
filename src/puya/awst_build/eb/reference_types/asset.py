from __future__ import annotations

import typing

from immutabledict import immutabledict

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    ReinterpretCast,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.reference_types.base import UInt64BackedReferenceValueExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


logger = log.get_logger(__name__)


class AssetClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.AssetType, location)

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
                uint64_expr: Expression = UInt64Constant(value=0, source_location=location)
            case [Literal(value=int(int_value))]:
                uint64_expr = UInt64Constant(value=int_value, source_location=location)
            case [ExpressionBuilder() as eb]:
                uint64_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                uint64_expr = UInt64Constant(value=0, source_location=location)
        asset_expr = ReinterpretCast(
            source_location=location, wtype=wtypes.asset_wtype, expr=uint64_expr
        )
        return AssetExpressionBuilder(asset_expr)


ASSET_HOLDING_FIELD_MAPPING: typing.Final = {
    "balance": ("AssetBalance", pytypes.UInt64Type),
    "frozen": ("AssetFrozen", pytypes.BoolType),
}


class AssetHoldingExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, asset: Expression, holding_field: str, location: SourceLocation):
        self.asset = asset
        self.holding_field = holding_field
        super().__init__(location)

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
            case [ExpressionBuilder() as eb]:
                account_expr = expect_operand_wtype(eb, wtypes.account_wtype)
                immediate, typ = ASSET_HOLDING_FIELD_MAPPING[self.holding_field]
                asset_params_get = IntrinsicCall(
                    source_location=location,
                    wtype=wtypes.WTuple((typ.wtype, wtypes.bool_wtype), location),
                    op_code="asset_holding_get",
                    immediates=[immediate],
                    stack_args=[account_expr, self.asset],
                )
                return builder_for_instance(
                    typ, CheckedMaybe(asset_params_get, comment="account opted into asset")
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AssetExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    wtype = wtypes.asset_wtype
    native_access_member = "id"
    field_mapping = immutabledict(
        {
            "total": ("AssetTotal", pytypes.UInt64Type),
            "decimals": ("AssetDecimals", pytypes.UInt64Type),
            "default_frozen": ("AssetDefaultFrozen", pytypes.BoolType),
            "unit_name": ("AssetUnitName", pytypes.BytesType),
            "name": ("AssetName", pytypes.BytesType),
            "url": ("AssetURL", pytypes.BytesType),
            "metadata_hash": ("AssetMetadataHash", pytypes.BytesType),
            "manager": ("AssetManager", pytypes.AccountType),
            "reserve": ("AssetReserve", pytypes.AccountType),
            "freeze": ("AssetFreeze", pytypes.AccountType),
            "clawback": ("AssetClawback", pytypes.AccountType),
            "creator": ("AssetCreator", pytypes.AccountType),
        }
    )
    field_op_code = "asset_params_get"
    field_bool_comment = "asset exists"

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name in ASSET_HOLDING_FIELD_MAPPING:
            return AssetHoldingExpressionBuilder(self.expr, name, location)
        return super().member_access(name, location)
