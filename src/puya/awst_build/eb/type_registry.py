import functools
from collections.abc import Callable

from puya.awst import wtypes
from puya.awst.nodes import Expression
from puya.awst_build import constants
from puya.awst_build.eb import (
    app_account_state,
    app_state,
    arc4,
    array,
    biguint,
    bool as bool_,
    bytes as bytes_,
    ensure_budget,
    intrinsics,
    named_int_constants,
    struct,
    transaction,
    tuple as tuple_,
    uint64,
    unsigned_builtins,
    void,
)
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.reference_types import account, application, asset
from puya.errors import InternalError
from puya.parse import SourceLocation

__all__ = [
    "get_type_builder",
    "var_expression",
]

ExpressionBuilderFromSourceFactory = Callable[[SourceLocation], ExpressionBuilder]
ExpressionBuilderFromExpressionFactory = Callable[[Expression], ExpressionBuilder]
CLS_NAME_TO_BUILDER: dict[str, ExpressionBuilderFromSourceFactory] = {
    "builtins.None": void.VoidTypeExpressionBuilder,
    "builtins.bool": bool_.BoolClassExpressionBuilder,
    "builtins.tuple": tuple_.TupleTypeExpressionBuilder,
    constants.URANGE: unsigned_builtins.UnsignedRangeBuilder,
    constants.UENUMERATE: unsigned_builtins.UnsignedEnumerateBuilder,
    constants.ARC4_SIGNATURE: intrinsics.Arc4SignatureBuilder,
    constants.ENSURE_BUDGET: ensure_budget.EnsureBudgetBuilder,
    constants.OP_UP_FEE_SOURCE: ensure_budget.OpUpFeeSourceClassBuilder,
    constants.CLS_LOCAL_STATE: app_account_state.AppAccountStateClassExpressionBuilder,
    constants.CLS_GLOBAL_STATE: app_state.AppStateClassExpressionBuilder,
    constants.CLS_ARC4_ADDRESS: arc4.AddressClassExpressionBuilder,
    constants.CLS_ARC4_BIG_UFIXEDNXM: arc4.UFixedNxMClassExpressionBuilder,
    constants.CLS_ARC4_BIG_UINTN: arc4.UIntNClassExpressionBuilder,
    constants.CLS_ARC4_BOOL: arc4.ARC4BoolClassExpressionBuilder,
    constants.CLS_ARC4_BYTE: arc4.ByteClassExpressionBuilder,
    constants.CLS_ARC4_DYNAMIC_ARRAY: arc4.DynamicArrayGenericClassExpressionBuilder,
    constants.CLS_ARC4_STATIC_ARRAY: arc4.StaticArrayGenericClassExpressionBuilder,
    constants.CLS_ARC4_STRING: arc4.StringClassExpressionBuilder,
    constants.CLS_ARC4_TUPLE: arc4.ARC4TupleGenericClassExpressionBuilder,
    constants.CLS_ARC4_UFIXEDNXM: arc4.UFixedNxMClassExpressionBuilder,
    constants.CLS_ARC4_UINTN: arc4.UIntNClassExpressionBuilder,
    constants.CLS_ACCOUNT: account.AccountClassExpressionBuilder,
    constants.CLS_ARRAY: array.ArrayGenericClassExpressionBuilder,
    constants.CLS_APPLICATION: application.ApplicationClassExpressionBuilder,
    constants.CLS_TRANSACTION_BASE: transaction.TransactionBaseClassExpressionBuilder,
    constants.CLS_APPLICATION_CALL_TRANSACTION: (
        transaction.ApplicationCallTransactionClassExpressionBuilder
    ),
    constants.CLS_ASSET: asset.AssetClassExpressionBuilder,
    constants.CLS_ASSET_CONFIG_TRANSACTION: (
        transaction.AssetConfigTransactionClassExpressionBuilder
    ),
    constants.CLS_ASSET_TRANSFER_TRANSACTION: (
        transaction.AssetTransferTransactionClassExpressionBuilder
    ),
    constants.CLS_ASSET_FREEZE_TRANSACTION: (
        transaction.AssetFreezeTransactionClassExpressionBuilder
    ),
    constants.CLS_BIGUINT: biguint.BigUIntClassExpressionBuilder,
    constants.CLS_BYTES: bytes_.BytesClassExpressionBuilder,
    constants.CLS_KEY_REGISTRATION_TRANSACTION: (
        transaction.KeyRegistrationTransactionClassExpressionBuilder
    ),
    constants.CLS_PAYMENT_TRANSACTION: transaction.PaymentTransactionClassExpressionBuilder,
    constants.CLS_UINT64: uint64.UInt64ClassExpressionBuilder,
    **{
        enum_name: functools.partial(
            named_int_constants.NamedIntegerConstsTypeBuilder,
            enum_name=enum_name,
            data=enum_data,
        )
        for enum_name, enum_data in constants.NAMED_INT_CONST_ENUM_DATA.items()
    },
}
WTYPE_TO_BUILDER: dict[
    wtypes.WType | type[wtypes.WType], ExpressionBuilderFromExpressionFactory
] = {
    wtypes.ARC4DynamicArray: arc4.DynamicArrayExpressionBuilder,
    wtypes.ARC4Struct: arc4.ARC4StructExpressionBuilder,
    wtypes.ARC4StaticArray: arc4.StaticArrayExpressionBuilder,
    wtypes.ARC4Tuple: arc4.ARC4TupleExpressionBuilder,
    wtypes.ARC4UFixedNxM: arc4.UFixedNxMExpressionBuilder,
    wtypes.ARC4UIntN: arc4.UIntNExpressionBuilder,
    wtypes.WArray: array.ArrayExpressionBuilder,
    wtypes.WStructType: struct.StructExpressionBuilder,
    wtypes.WTuple: tuple_.TupleExpressionBuilder,
    wtypes.arc4_bool_wtype: arc4.ARC4BoolExpressionBuilder,
    wtypes.arc4_string_wtype: arc4.StringExpressionBuilder,
    wtypes.account_wtype: account.AccountExpressionBuilder,
    wtypes.application_wtype: application.ApplicationExpressionBuilder,
    wtypes.application_call_wtype: transaction.ApplicationCallTransactionExpressionBuilder,
    wtypes.asset_config_wtype: transaction.AssetConfigTransactionExpressionBuilder,
    wtypes.asset_transfer_wtype: transaction.AssetTransferTransactionExpressionBuilder,
    wtypes.asset_freeze_wtype: transaction.AssetFreezeTransactionExpressionBuilder,
    wtypes.transaction_base_wtype: transaction.TransactionBaseExpressionBuilder,
    wtypes.asset_wtype: asset.AssetExpressionBuilder,
    wtypes.biguint_wtype: biguint.BigUIntExpressionBuilder,
    wtypes.bool_wtype: bool_.BoolExpressionBuilder,
    wtypes.bytes_wtype: bytes_.BytesExpressionBuilder,
    wtypes.key_registration_wtype: transaction.KeyRegistrationTransactionExpressionBuilder,
    wtypes.payment_wtype: transaction.PaymentTransactionExpressionBuilder,
    wtypes.uint64_wtype: uint64.UInt64ExpressionBuilder,
    wtypes.void_wtype: void.VoidExpressionBuilder,
}


def get_type_builder(python_type: str, source_location: SourceLocation) -> ExpressionBuilder:
    try:
        type_class = CLS_NAME_TO_BUILDER[python_type]
    except KeyError as ex:
        raise InternalError(f"Unhandled puyapy name: {python_type}", source_location) from ex
    else:
        return type_class(source_location)


def var_expression(expr: Expression) -> ExpressionBuilder:
    try:
        builder = WTYPE_TO_BUILDER[expr.wtype]
    except KeyError:
        builder = WTYPE_TO_BUILDER[type(expr.wtype)]
    return builder(expr)
