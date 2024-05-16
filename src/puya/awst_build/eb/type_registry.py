import functools
from collections.abc import Callable

import puya.awst_build.eb.arc4.dynamic_bytes
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
    box,
    bytes as bytes_,
    ensure_budget,
    intrinsics,
    log,
    named_int_constants,
    string,
    struct,
    template_variables,
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
ExpressionBuilderFromTypeAndSourceFactory = Callable[
    [wtypes.WType, SourceLocation], ExpressionBuilder
]
ExpressionBuilderFromExpressionFactory = Callable[[Expression], ExpressionBuilder]
CLS_NAME_TO_BUILDER: dict[str, ExpressionBuilderFromSourceFactory] = {
    "builtins.None": void.VoidTypeExpressionBuilder,
    "builtins.bool": bool_.BoolClassExpressionBuilder,
    "builtins.tuple": tuple_.GenericTupleTypeExpressionBuilder,
    constants.URANGE: unsigned_builtins.UnsignedRangeBuilder,
    constants.UENUMERATE: unsigned_builtins.UnsignedEnumerateBuilder,
    constants.ARC4_SIGNATURE: intrinsics.Arc4SignatureBuilder,
    constants.ENSURE_BUDGET: ensure_budget.EnsureBudgetBuilder,
    constants.LOG: log.LogBuilder,
    constants.EMIT: arc4.EmitBuilder,
    constants.OP_UP_FEE_SOURCE: ensure_budget.OpUpFeeSourceClassBuilder,
    constants.CLS_BOX_PROXY: box.BoxClassGenericExpressionBuilder,
    constants.CLS_BOX_REF_PROXY: box.BoxRefClassExpressionBuilder,
    constants.CLS_BOX_MAP_PROXY: box.BoxMapClassGenericExpressionBuilder,
    constants.CLS_LOCAL_STATE: app_account_state.AppAccountStateClassExpressionBuilder,
    constants.CLS_GLOBAL_STATE: app_state.AppStateClassExpressionBuilder,
    constants.CLS_ARC4_ADDRESS: arc4.AddressClassExpressionBuilder,
    constants.CLS_ARC4_BOOL: arc4.ARC4BoolClassExpressionBuilder,
    constants.CLS_ARC4_BYTE: arc4.ByteClassExpressionBuilder,
    constants.CLS_ARC4_DYNAMIC_ARRAY: arc4.DynamicArrayGenericClassExpressionBuilder,
    constants.CLS_ARC4_STATIC_ARRAY: arc4.StaticArrayGenericClassExpressionBuilder,
    constants.CLS_ARC4_STRING: arc4.StringClassExpressionBuilder,
    constants.CLS_ARC4_TUPLE: arc4.ARC4TupleGenericClassExpressionBuilder,
    constants.CLS_ARC4_ABI_CALL: arc4.ABICallGenericClassExpressionBuilder,
    constants.CLS_ARC4_DYNAMIC_BYTES: puya.awst_build.eb.arc4.DynamicBytesClassExpressionBuilder,
    constants.CLS_ACCOUNT: account.AccountClassExpressionBuilder,
    constants.CLS_ARRAY: array.ArrayGenericClassExpressionBuilder,
    constants.CLS_ASSET: asset.AssetClassExpressionBuilder,
    constants.CLS_APPLICATION: application.ApplicationClassExpressionBuilder,
    constants.CLS_BIGUINT: biguint.BigUIntClassExpressionBuilder,
    constants.CLS_BYTES: bytes_.BytesClassExpressionBuilder,
    constants.CLS_STRING: string.StringClassExpressionBuilder,
    constants.CLS_UINT64: uint64.UInt64ClassExpressionBuilder,
    constants.CLS_TEMPLATE_VAR_METHOD: (
        template_variables.GenericTemplateVariableExpressionBuilder
    ),
    constants.SUBMIT_TXNS: transaction.SubmitInnerTransactionExpressionBuilder,
    constants.CLS_TRANSACTION_BASE: functools.partial(
        transaction.GroupTransactionClassExpressionBuilder,
        wtype=wtypes.WGroupTransaction(
            transaction_type=None,
            stub_name=constants.CLS_TRANSACTION_BASE,
            name="group_transaction_base",
        ),
    ),
    **{
        txn_cls.gtxn: functools.partial(
            transaction.GroupTransactionClassExpressionBuilder,
            wtype=wtypes.WGroupTransaction.from_type(txn_type),
        )
        for txn_type, txn_cls in constants.TRANSACTION_TYPE_TO_CLS.items()
    },
    **{
        txn_cls.itxn_fields: functools.partial(
            transaction.InnerTxnParamsClassExpressionBuilder,
            wtype=wtypes.WInnerTransactionFields.from_type(txn_type),
        )
        for txn_type, txn_cls in constants.TRANSACTION_TYPE_TO_CLS.items()
    },
    **{
        txn_cls.itxn_result: functools.partial(
            transaction.InnerTransactionClassExpressionBuilder,
            wtype=wtypes.WInnerTransaction.from_type(txn_type),
        )
        for txn_type, txn_cls in constants.TRANSACTION_TYPE_TO_CLS.items()
    },
    **{
        enum_name: functools.partial(
            named_int_constants.NamedIntegerConstsTypeBuilder,
            enum_name=enum_name,
            data=enum_data,
        )
        for enum_name, enum_data in constants.NAMED_INT_CONST_ENUM_DATA.items()
    },
}
WTYPE_TO_TYPE_BUILDER: dict[type[wtypes.WType], ExpressionBuilderFromTypeAndSourceFactory] = {
    wtypes.WTuple: tuple_.TupleTypeExpressionBuilder,
    wtypes.WArray: array.ArrayClassExpressionBuilder,
    wtypes.ARC4UFixedNxM: arc4.UFixedNxMClassExpressionBuilder,
    wtypes.ARC4UIntN: arc4.UIntNClassExpressionBuilder,
    wtypes.ARC4DynamicArray: arc4.DynamicArrayClassExpressionBuilder,
    wtypes.ARC4StaticArray: arc4.StaticArrayClassExpressionBuilder,
    wtypes.ARC4Tuple: arc4.ARC4TupleClassExpressionBuilder,
    wtypes.WBoxProxy: box.BoxClassExpressionBuilder,
    wtypes.WBoxMapProxy: box.BoxMapClassExpressionBuilder,
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
    wtypes.arc4_dynamic_bytes: arc4.DynamicBytesExpressionBuilder,
    wtypes.arc4_address_type: arc4.AddressExpressionBuilder,
    wtypes.account_wtype: account.AccountExpressionBuilder,
    wtypes.application_wtype: application.ApplicationExpressionBuilder,
    wtypes.asset_wtype: asset.AssetExpressionBuilder,
    wtypes.biguint_wtype: biguint.BigUIntExpressionBuilder,
    wtypes.bool_wtype: bool_.BoolExpressionBuilder,
    wtypes.bytes_wtype: bytes_.BytesExpressionBuilder,
    wtypes.string_wtype: string.StringExpressionBuilder,
    wtypes.uint64_wtype: uint64.UInt64ExpressionBuilder,
    wtypes.void_wtype: void.VoidExpressionBuilder,
    wtypes.WGroupTransaction: transaction.GroupTransactionExpressionBuilder,
    wtypes.WInnerTransaction: transaction.InnerTransactionExpressionBuilder,
    wtypes.WInnerTransactionFields: transaction.InnerTxnParamsExpressionBuilder,
    wtypes.WBoxProxy: box.BoxProxyExpressionBuilder,
    wtypes.WBoxMapProxy: box.BoxMapProxyExpressionBuilder,
    wtypes.box_ref_proxy_type: box.BoxRefProxyExpressionBuilder,
}


def get_type_builder(python_type: str, source_location: SourceLocation) -> ExpressionBuilder:
    try:
        type_class = CLS_NAME_TO_BUILDER[python_type]
    except KeyError as ex:
        raise InternalError(f"Unhandled algopy name: {python_type}", source_location) from ex
    else:
        return type_class(source_location)


def var_expression(expr: Expression) -> ExpressionBuilder:
    try:
        builder = WTYPE_TO_BUILDER[expr.wtype]
    except KeyError:
        try:
            builder = WTYPE_TO_BUILDER[type(expr.wtype)]
        except KeyError:
            raise InternalError(
                f"Unable to map wtype {expr.wtype!r} to expression builder", expr.source_location
            ) from None
    return builder(expr)
