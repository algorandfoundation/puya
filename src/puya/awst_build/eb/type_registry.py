import functools
from collections.abc import Callable

import puya.awst_build.eb.arc4.dynamic_bytes
from puya.awst import wtypes
from puya.awst.nodes import Expression
from puya.awst_build import constants, pytypes
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
    "var_expression",
    "builder_for_instance",
    "builder_for_type",
]

ExpressionBuilderFromSourceFactory = Callable[[SourceLocation], ExpressionBuilder]
ExpressionBuilderFromPyTypeAndSourceFactory = Callable[
    [pytypes.PyType, SourceLocation], ExpressionBuilder
]
FUNC_NAME_TO_BUILDER: dict[str, ExpressionBuilderFromSourceFactory] = {
    constants.ARC4_SIGNATURE: intrinsics.Arc4SignatureBuilder,
    constants.ENSURE_BUDGET: ensure_budget.EnsureBudgetBuilder,
    constants.LOG: log.LogBuilder,
    constants.EMIT: arc4.EmitBuilder,
    constants.SUBMIT_TXNS: transaction.SubmitInnerTransactionExpressionBuilder,
    constants.CLS_ARC4_ABI_CALL: arc4.ABICallGenericClassExpressionBuilder,
    constants.CLS_TEMPLATE_VAR_METHOD: (
        template_variables.GenericTemplateVariableExpressionBuilder
    ),
}
PYTYPE_TO_TYPE_BUILDER: dict[pytypes.PyType, ExpressionBuilderFromSourceFactory] = {
    pytypes.NoneType: void.VoidTypeExpressionBuilder,
    pytypes.BoolType: bool_.BoolClassExpressionBuilder,
    pytypes.GenericTupleType: tuple_.GenericTupleTypeExpressionBuilder,
    pytypes.reversedGenericType: functools.partial(
        unsigned_builtins.ReversedFunctionExpressionBuilder, None
    ),
    pytypes.urangeType: unsigned_builtins.UnsignedRangeBuilder,
    pytypes.uenumerateGenericType: functools.partial(
        unsigned_builtins.UnsignedEnumerateBuilder, None
    ),
    pytypes.OpUpFeeSourceType: ensure_budget.OpUpFeeSourceClassBuilder,
    pytypes.GenericBoxType: box.BoxClassGenericExpressionBuilder,
    pytypes.BoxRefType: box.BoxRefClassExpressionBuilder,
    pytypes.GenericBoxMapType: box.BoxMapClassGenericExpressionBuilder,
    pytypes.GenericLocalStateType: app_account_state.AppAccountStateGenericClassExpressionBuilder,
    pytypes.GenericGlobalStateType: app_state.AppStateGenericClassExpressionBuilder,
    pytypes.ARC4AddressType: arc4.AddressClassExpressionBuilder,
    pytypes.ARC4BoolType: arc4.ARC4BoolClassExpressionBuilder,
    pytypes.ARC4ByteType: arc4.ByteClassExpressionBuilder,
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayGenericClassExpressionBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayGenericClassExpressionBuilder,
    pytypes.ARC4StringType: arc4.StringClassExpressionBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleGenericClassExpressionBuilder,
    pytypes.ARC4DynamicBytesType: puya.awst_build.eb.arc4.DynamicBytesClassExpressionBuilder,
    pytypes.AccountType: account.AccountClassExpressionBuilder,
    pytypes.GenericArrayType: array.ArrayGenericClassExpressionBuilder,
    pytypes.AssetType: asset.AssetClassExpressionBuilder,
    pytypes.ApplicationType: application.ApplicationClassExpressionBuilder,
    pytypes.BigUIntType: biguint.BigUIntClassExpressionBuilder,
    pytypes.BytesType: bytes_.BytesClassExpressionBuilder,
    pytypes.StringType: string.StringClassExpressionBuilder,
    pytypes.UInt64Type: uint64.UInt64ClassExpressionBuilder,
    **{
        gtxn_pytyp: functools.partial(
            transaction.GroupTransactionClassExpressionBuilder, wtype=gtxn_pytyp.wtype
        )
        for gtxn_pytyp in (
            pytypes.GroupTransactionBaseType,
            *pytypes.GroupTransactionTypes.values(),
        )
    },
    **{
        itxn_fieldset_pytyp: functools.partial(
            transaction.InnerTxnParamsClassExpressionBuilder, wtype=itxn_fieldset_pytyp.wtype
        )
        for itxn_fieldset_pytyp in pytypes.InnerTransactionFieldsetTypes.values()
    },
    **{
        itxn_result_pytyp: functools.partial(
            transaction.InnerTransactionClassExpressionBuilder, wtype=itxn_result_pytyp.wtype
        )
        for itxn_result_pytyp in pytypes.InnerTransactionResultTypes.values()
    },
}
PYTYPE_GENERIC_TO_TYPE_BUILDER: dict[
    pytypes.PyType | None, ExpressionBuilderFromPyTypeAndSourceFactory
] = {
    pytypes.uenumerateGenericType: unsigned_builtins.UnsignedEnumerateBuilder,
    pytypes.reversedGenericType: unsigned_builtins.ReversedFunctionExpressionBuilder,
    pytypes.GenericTemplateVarType: template_variables.TemplateVariableExpressionBuilder,
    pytypes.GenericABICallWithReturnType: arc4.ABICallClassExpressionBuilder,
    pytypes.GenericLocalStateType: app_account_state.AppAccountStateClassExpressionBuilder,
    pytypes.GenericGlobalStateType: app_state.AppStateClassExpressionBuilder,
    pytypes.GenericBoxType: box.BoxClassExpressionBuilder,
    pytypes.GenericBoxMapType: box.BoxMapClassExpressionBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleClassExpressionBuilder,
    pytypes.GenericTupleType: tuple_.TupleTypeExpressionBuilder,
    pytypes.GenericArrayType: array.ArrayClassExpressionBuilder,
    pytypes.GenericARC4UFixedNxMType: arc4.UFixedNxMClassExpressionBuilder,
    pytypes.GenericARC4BigUFixedNxMType: arc4.UFixedNxMClassExpressionBuilder,
    pytypes.GenericARC4UIntNType: arc4.UIntNClassExpressionBuilder,
    pytypes.GenericARC4BigUIntNType: arc4.UIntNClassExpressionBuilder,
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayClassExpressionBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayClassExpressionBuilder,
}
PYTYPE_BASE_TO_TYPE_BUILDER: dict[pytypes.PyType, ExpressionBuilderFromPyTypeAndSourceFactory] = {
    pytypes.ARC4StructBaseType: arc4.ARC4StructClassExpressionBuilder,
    pytypes.StructBaseType: struct.StructSubclassExpressionBuilder,
}

ExpressionBuilderFromExpressionFactory = Callable[[Expression], ExpressionBuilder]
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
}


PYTYPE_TO_BUILDER: dict[pytypes.PyType, ExpressionBuilderFromExpressionFactory] = {
    pytypes.ARC4BoolType: arc4.ARC4BoolExpressionBuilder,
    pytypes.ARC4StringType: arc4.StringExpressionBuilder,
    pytypes.ARC4DynamicBytesType: arc4.DynamicBytesExpressionBuilder,
    pytypes.ARC4ByteType: arc4.UIntNExpressionBuilder,
    pytypes.ARC4AddressType: arc4.AddressExpressionBuilder,
    pytypes.AccountType: account.AccountExpressionBuilder,
    pytypes.ApplicationType: application.ApplicationExpressionBuilder,
    pytypes.AssetType: asset.AssetExpressionBuilder,
    pytypes.BigUIntType: biguint.BigUIntExpressionBuilder,
    pytypes.BoolType: bool_.BoolExpressionBuilder,
    pytypes.BytesType: bytes_.BytesExpressionBuilder,
    pytypes.StringType: string.StringExpressionBuilder,
    pytypes.UInt64Type: uint64.UInt64ExpressionBuilder,
    pytypes.NoneType: void.VoidExpressionBuilder,
    pytypes.BoxRefType: box.BoxRefProxyExpressionBuilder,
    # bound
    **{
        gtxn_pytyp: functools.partial(
            transaction.GroupTransactionExpressionBuilder, typ=gtxn_pytyp
        )
        for gtxn_pytyp in (
            pytypes.GroupTransactionBaseType,
            *pytypes.GroupTransactionTypes.values(),
        )
    },
    **{
        itxn_fieldset_pytyp: functools.partial(
            transaction.InnerTxnParamsExpressionBuilder, typ=itxn_fieldset_pytyp
        )
        for itxn_fieldset_pytyp in pytypes.InnerTransactionFieldsetTypes.values()
    },
    **{
        itxn_result_pytyp: functools.partial(
            transaction.InnerTransactionExpressionBuilder, typ=itxn_result_pytyp
        )
        for itxn_result_pytyp in pytypes.InnerTransactionResultTypes.values()
    },
}
ExpressionBuilderFromExpressionAndPyTypeFactory = Callable[
    [Expression, pytypes.PyType], ExpressionBuilder
]
PYTYPE_GENERIC_TO_BUILDER: dict[
    pytypes.PyType | None, ExpressionBuilderFromExpressionAndPyTypeFactory
] = {
    pytypes.GenericTupleType: tuple_.TupleExpressionBuilder,
    pytypes.GenericBoxType: box.BoxProxyExpressionBuilder,
    pytypes.GenericBoxMapType: box.BoxMapProxyExpressionBuilder,
    pytypes.GenericArrayType: array.ArrayExpressionBuilder,
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayExpressionBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayExpressionBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleExpressionBuilder,
    pytypes.GenericARC4UFixedNxMType: arc4.UFixedNxMExpressionBuilder,
    pytypes.GenericARC4BigUFixedNxMType: arc4.UFixedNxMExpressionBuilder,
    pytypes.GenericARC4UIntNType: arc4.UIntNExpressionBuilder,
    pytypes.GenericARC4BigUIntNType: arc4.UIntNExpressionBuilder,
    pytypes.GenericGlobalStateType: app_state.AppStateExpressionBuilder,
    pytypes.GenericLocalStateType: app_account_state.AppAccountStateExpressionBuilder,
}
PYTYPE_BASE_TO_BUILDER: dict[pytypes.PyType, ExpressionBuilderFromExpressionAndPyTypeFactory] = {
    pytypes.ARC4StructBaseType: arc4.ARC4StructExpressionBuilder,
    pytypes.StructBaseType: struct.StructExpressionBuilder,
}


def builder_for_instance(pytyp: pytypes.PyType, expr: Expression) -> ExpressionBuilder:
    if eb := PYTYPE_TO_BUILDER.get(pytyp):
        return eb(expr)
    if eb_param_generic := PYTYPE_GENERIC_TO_BUILDER.get(pytyp.generic):
        return eb_param_generic(expr, pytyp)
    for base in pytyp.mro:
        if eb_base := PYTYPE_BASE_TO_BUILDER.get(base):
            return eb_base(expr, pytyp)
    raise InternalError(f"No builder for instance: {pytyp}", expr.source_location)


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


def builder_for_type(pytyp: pytypes.PyType, expr_loc: SourceLocation) -> ExpressionBuilder:
    if tb := PYTYPE_TO_TYPE_BUILDER.get(pytyp):
        return tb(expr_loc)
    if tb_param_generic := PYTYPE_GENERIC_TO_TYPE_BUILDER.get(pytyp.generic):
        return tb_param_generic(pytyp, expr_loc)
    for base in pytyp.mro:
        if tb_base := PYTYPE_BASE_TO_TYPE_BUILDER.get(base):
            return tb_base(pytyp, expr_loc)
    raise InternalError(f"No builder for type: {pytyp}", expr_loc)
