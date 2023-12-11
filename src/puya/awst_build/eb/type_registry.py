from puya.awst import (
    wtypes,
)
from puya.awst.nodes import Expression
from puya.awst_build import constants
from puya.awst_build.eb import (
    arc4,
    array,
    biguint,
    bool as bool_,
    bytes as bytes_,
    struct,
    transaction,
    tuple as tuple_,
    uint64,
    void,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.reference_types import account, application, asset
from puya.errors import CodeError
from puya.parse import SourceLocation

TYPE_NAME_CLS_MAPPING: dict[
    str, type[TypeClassExpressionBuilder | GenericClassExpressionBuilder]
] = {
    "builtins.None": void.VoidTypeExpressionBuilder,
    "builtins.bool": bool_.BoolClassExpressionBuilder,
    "builtins.tuple": tuple_.TupleTypeExpressionBuilder,
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
}

WTYPE_BUILDER_MAPPING = {
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


def get_type_builder(
    python_type: str, source_location: SourceLocation
) -> TypeClassExpressionBuilder | GenericClassExpressionBuilder:
    try:
        type_class = TYPE_NAME_CLS_MAPPING[python_type]
    except KeyError as ex:
        # TODO: make an InternalError before alpha
        raise CodeError(f"Unhandled puyapy name: {python_type}", source_location) from ex
    else:
        return type_class(source_location)


def var_expression(expr: Expression) -> ExpressionBuilder:
    try:
        builder = WTYPE_BUILDER_MAPPING[expr.wtype]
    except KeyError:
        builder = WTYPE_BUILDER_MAPPING[type(expr.wtype)]
    return builder(expr)
