import functools
from collections.abc import Callable

from puya.awst.nodes import Expression
from puya.awst_build import constants, intrinsic_data, pytypes
from puya.awst_build.eb import (
    arc4,
    array,
    biguint,
    bool as bool_,
    bytes as bytes_,
    ensure_budget,
    intrinsics,
    log,
    storage,
    string,
    struct,
    template_variables,
    transaction,
    tuple as tuple_,
    uint64,
    unsigned_builtins,
    void,
)
from puya.awst_build.eb.interface import CallableBuilder, InstanceBuilder
from puya.awst_build.eb.reference_types import account, application, asset
from puya.errors import InternalError
from puya.parse import SourceLocation

__all__ = [
    "builder_for_instance",
    "builder_for_type",
]

CallableBuilderFromSourceFactory = Callable[[SourceLocation], CallableBuilder]

FUNC_NAME_TO_BUILDER: dict[str, CallableBuilderFromSourceFactory] = {
    constants.ARC4_SIGNATURE: intrinsics.Arc4SignatureBuilder,
    constants.ENSURE_BUDGET: ensure_budget.EnsureBudgetBuilder,
    constants.LOG: log.LogBuilder,
    constants.EMIT: arc4.EmitBuilder,
    constants.SUBMIT_TXNS: transaction.SubmitInnerTransactionExpressionBuilder,
    constants.CLS_ARC4_ABI_CALL: arc4.ABICallGenericTypeBuilder,
    constants.CLS_TEMPLATE_VAR_METHOD: (
        template_variables.GenericTemplateVariableExpressionBuilder
    ),
    **{
        (fullname := "".join((constants.ALGOPY_OP_PREFIX, name))): functools.partial(
            intrinsics.IntrinsicFunctionExpressionBuilder, fullname, mappings
        )
        for name, mappings in intrinsic_data.FUNC_TO_AST_MAPPER.items()
    },
}

PYTYPE_TO_TYPE_BUILDER: dict[pytypes.PyType, CallableBuilderFromSourceFactory] = {
    pytypes.NoneType: void.VoidTypeExpressionBuilder,
    pytypes.BoolType: bool_.BoolTypeBuilder,
    pytypes.GenericTupleType: tuple_.GenericTupleTypeExpressionBuilder,
    pytypes.reversedGenericType: functools.partial(
        unsigned_builtins.ReversedFunctionExpressionBuilder, None
    ),
    pytypes.urangeType: unsigned_builtins.UnsignedRangeBuilder,
    pytypes.uenumerateGenericType: functools.partial(
        unsigned_builtins.UnsignedEnumerateBuilder, None
    ),
    pytypes.OpUpFeeSourceType: ensure_budget.OpUpFeeSourceClassBuilder,
    pytypes.GenericBoxType: storage.BoxClassGenericExpressionBuilder,
    pytypes.BoxRefType: storage.BoxRefTypeBuilder,
    pytypes.GenericBoxMapType: storage.BoxMapClassGenericExpressionBuilder,
    pytypes.GenericLocalStateType: storage.LocalStateGenericTypeBuilder,
    pytypes.GenericGlobalStateType: storage.GlobalStateGenericTypeBuilder,
    pytypes.ARC4AddressType: arc4.AddressTypeBuilder,
    pytypes.ARC4BoolType: arc4.ARC4BoolTypeBuilder,
    pytypes.ARC4ByteType: functools.partial(arc4.UIntNTypeBuilder, pytypes.ARC4ByteType),
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayGenericTypeBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayGenericTypeBuilder,
    pytypes.ARC4StringType: arc4.StringTypeBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleGenericTypeBuilder,
    pytypes.ARC4DynamicBytesType: arc4.DynamicBytesTypeBuilder,
    pytypes.AccountType: account.AccountTypeBuilder,
    pytypes.GenericArrayType: array.ArrayGenericTypeBuilder,
    pytypes.AssetType: asset.AssetTypeBuilder,
    pytypes.ApplicationType: application.ApplicationTypeBuilder,
    pytypes.BigUIntType: biguint.BigUIntTypeBuilder,
    pytypes.BytesType: bytes_.BytesTypeBuilder,
    pytypes.StringType: string.StringTypeBuilder,
    pytypes.UInt64Type: uint64.UInt64TypeBuilder,
    **{
        op_enum_typ: functools.partial(intrinsics.IntrinsicEnumTypeBuilder, op_enum_typ)
        for op_enum_typ in pytypes.OpEnumTypes
    },
    **{
        op_namespace_typ: functools.partial(
            intrinsics.IntrinsicNamespaceTypeBuilder, op_namespace_typ
        )
        for op_namespace_typ in pytypes.OpNamespaceTypes
    },
    **{
        gtxn_pytyp: functools.partial(transaction.GroupTransactionTypeBuilder, gtxn_pytyp)
        for gtxn_pytyp in (
            pytypes.GroupTransactionBaseType,
            *pytypes.GroupTransactionTypes.values(),
        )
    },
    **{
        itxn_fieldset_pytyp: functools.partial(
            transaction.InnerTxnParamsTypeBuilder, itxn_fieldset_pytyp
        )
        for itxn_fieldset_pytyp in pytypes.InnerTransactionFieldsetTypes.values()
    },
    **{
        itxn_result_pytyp: functools.partial(
            transaction.InnerTransactionTypeBuilder, itxn_result_pytyp
        )
        for itxn_result_pytyp in pytypes.InnerTransactionResultTypes.values()
    },
}

CallableBuilderFromPyTypeAndSourceFactory = Callable[
    [pytypes.PyType, SourceLocation], CallableBuilder
]

PYTYPE_GENERIC_TO_TYPE_BUILDER: dict[
    pytypes.PyType | None, CallableBuilderFromPyTypeAndSourceFactory
] = {
    pytypes.uenumerateGenericType: unsigned_builtins.UnsignedEnumerateBuilder,
    pytypes.reversedGenericType: unsigned_builtins.ReversedFunctionExpressionBuilder,
    pytypes.GenericTemplateVarType: template_variables.TemplateVariableExpressionBuilder,
    pytypes.GenericABICallWithReturnType: arc4.ABICallTypeBuilder,
    pytypes.GenericLocalStateType: storage.LocalStateTypeBuilder,
    pytypes.GenericGlobalStateType: storage.GlobalStateTypeBuilder,
    pytypes.GenericBoxType: storage.BoxTypeBuilder,
    pytypes.GenericBoxMapType: storage.BoxMapTypeBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleTypeBuilder,
    pytypes.GenericTupleType: tuple_.TupleTypeExpressionBuilder,
    pytypes.GenericArrayType: array.ArrayTypeBuilder,
    pytypes.GenericARC4UFixedNxMType: arc4.UFixedNxMTypeBuilder,
    pytypes.GenericARC4BigUFixedNxMType: arc4.UFixedNxMTypeBuilder,
    pytypes.GenericARC4UIntNType: arc4.UIntNTypeBuilder,
    pytypes.GenericARC4BigUIntNType: arc4.UIntNTypeBuilder,
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayTypeBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayTypeBuilder,
}

PYTYPE_BASE_TO_TYPE_BUILDER: dict[pytypes.PyType, CallableBuilderFromPyTypeAndSourceFactory] = {
    pytypes.ARC4StructBaseType: arc4.ARC4StructTypeBuilder,
    pytypes.StructBaseType: struct.StructSubclassExpressionBuilder,
}

PYTYPE_TO_BUILDER: dict[pytypes.PyType, Callable[[Expression], InstanceBuilder]] = {
    pytypes.ARC4BoolType: arc4.ARC4BoolExpressionBuilder,
    pytypes.ARC4StringType: arc4.StringExpressionBuilder,
    pytypes.ARC4DynamicBytesType: arc4.DynamicBytesExpressionBuilder,
    pytypes.ARC4ByteType: functools.partial(arc4.UIntNExpressionBuilder, typ=pytypes.ARC4ByteType),
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
    pytypes.BoxRefType: storage.BoxRefProxyExpressionBuilder,
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

InstanceBuilderFromExpressionAndPyTypeFactory = Callable[
    [Expression, pytypes.PyType], InstanceBuilder
]

PYTYPE_GENERIC_TO_BUILDER: dict[
    pytypes.PyType | None, InstanceBuilderFromExpressionAndPyTypeFactory
] = {
    pytypes.GenericTupleType: tuple_.TupleExpressionBuilder,
    pytypes.GenericBoxType: storage.BoxProxyExpressionBuilder,
    pytypes.GenericBoxMapType: storage.BoxMapProxyExpressionBuilder,
    pytypes.GenericArrayType: array.ArrayExpressionBuilder,
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayExpressionBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayExpressionBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleExpressionBuilder,
    pytypes.GenericARC4UFixedNxMType: arc4.UFixedNxMExpressionBuilder,
    pytypes.GenericARC4BigUFixedNxMType: arc4.UFixedNxMExpressionBuilder,
    pytypes.GenericARC4UIntNType: arc4.UIntNExpressionBuilder,
    pytypes.GenericARC4BigUIntNType: arc4.UIntNExpressionBuilder,
    pytypes.GenericGlobalStateType: storage.GlobalStateExpressionBuilder,
    pytypes.GenericLocalStateType: storage.LocalStateExpressionBuilder,
}

PYTYPE_BASE_TO_BUILDER: dict[pytypes.PyType, InstanceBuilderFromExpressionAndPyTypeFactory] = {
    pytypes.ARC4StructBaseType: arc4.ARC4StructExpressionBuilder,
    pytypes.StructBaseType: struct.StructExpressionBuilder,
}


def builder_for_instance(pytyp: pytypes.PyType, expr: Expression) -> InstanceBuilder:
    if eb := PYTYPE_TO_BUILDER.get(pytyp):
        return eb(expr)
    if eb_param_generic := PYTYPE_GENERIC_TO_BUILDER.get(pytyp.generic):
        return eb_param_generic(expr, pytyp)
    for base in pytyp.mro:
        if eb_base := PYTYPE_BASE_TO_BUILDER.get(base):
            return eb_base(expr, pytyp)
    raise InternalError(f"No builder for instance: {pytyp}", expr.source_location)


def builder_for_type(pytyp: pytypes.PyType, expr_loc: SourceLocation) -> CallableBuilder:
    if tb := PYTYPE_TO_TYPE_BUILDER.get(pytyp):
        return tb(expr_loc)
    if tb_param_generic := PYTYPE_GENERIC_TO_TYPE_BUILDER.get(pytyp.generic):
        return tb_param_generic(pytyp, expr_loc)
    for base in pytyp.mro:
        if tb_base := PYTYPE_BASE_TO_TYPE_BUILDER.get(base):
            return tb_base(pytyp, expr_loc)
    raise InternalError(f"No builder for type: {pytyp}", expr_loc)
