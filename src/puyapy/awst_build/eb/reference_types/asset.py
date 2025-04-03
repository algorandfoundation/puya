import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    ReinterpretCast,
    UInt64Constant,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.reference_types._base import UInt64BackedReferenceValueExpressionBuilder

logger = log.get_logger(__name__)


class AssetTypeBuilder(TypeBuilder[pytypes.RuntimeType]):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.AssetType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case int(int_value):
                if int_value < 0 or int_value.bit_length() > 64:  # TODO: should this be 256?
                    logger.error("invalid asset ID", location=literal.source_location)
                const = UInt64Constant(value=int_value, source_location=location)
                expr = ReinterpretCast(
                    expr=const, wtype=self.produces().wtype, source_location=location
                )
                return AssetExpressionBuilder(expr)
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
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                return arg.resolve_literal(AssetTypeBuilder(location))
            case None:
                uint64_expr: Expression = UInt64Constant(value=0, source_location=location)
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.UInt64Type)
                uint64_expr = arg.resolve()
        asset_expr = ReinterpretCast(
            expr=uint64_expr, wtype=wtypes.asset_wtype, source_location=location
        )
        return AssetExpressionBuilder(asset_expr)


ASSET_HOLDING_FIELD_MAPPING: typing.Final = {
    "balance": ("AssetBalance", pytypes.UInt64Type),
    "frozen": ("AssetFrozen", pytypes.BoolType),
}


class AssetHoldingExpressionBuilder(FunctionBuilder):
    def __init__(self, asset: Expression, holding_field: str, location: SourceLocation):
        self.asset = asset
        self.holding_field = holding_field
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, pytypes.AccountType, location)
        account_expr = arg.resolve()
        immediate, typ = ASSET_HOLDING_FIELD_MAPPING[self.holding_field]
        asset_params_get = IntrinsicCall(
            source_location=location,
            wtype=wtypes.WTuple(types=(typ.wtype, wtypes.bool_wtype), source_location=location),
            op_code="asset_holding_get",
            immediates=[immediate],
            stack_args=[account_expr, self.asset],
        )
        return builder_for_instance(
            typ, CheckedMaybe(asset_params_get, comment="account opted into asset")
        )


class AssetExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    def __init__(self, expr: Expression):
        native_access_member = "id"
        field_mapping = {
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
        field_op_code = "asset_params_get"
        field_bool_comment = "asset exists"
        super().__init__(
            expr,
            typ=pytypes.AssetType,
            typ_literal_converter=AssetTypeBuilder,
            native_access_member=native_access_member,
            field_mapping=field_mapping,
            field_op_code=field_op_code,
            field_bool_comment=field_bool_comment,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name in ASSET_HOLDING_FIELD_MAPPING:
            return AssetHoldingExpressionBuilder(self.resolve(), name, location)
        return super().member_access(name, location)
