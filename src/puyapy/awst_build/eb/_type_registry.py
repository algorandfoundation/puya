import functools
from collections.abc import Callable

from puya.awst.nodes import Expression
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build import constants, intrinsic_data, pytypes
from puyapy.awst_build.eb import (
    arc4,
    array,
    biguint,
    bool as bool_,
    bytes as bytes_,
    compiled,
    ensure_budget,
    immutable_array,
    intrinsics,
    log,
    none,
    size_of,
    storage,
    string,
    struct,
    template_variables,
    transaction,
    tuple as tuple_,
    uint64,
    uint64_enums,
    unsigned_builtins,
)
from puyapy.awst_build.eb.interface import CallableBuilder, InstanceBuilder
from puyapy.awst_build.eb.reference_types import account, application, asset

__all__ = [
    "builder_for_instance",
    "builder_for_type",
]

CallableBuilderFromSourceFactory = Callable[[SourceLocation], CallableBuilder]

FUNC_NAME_TO_BUILDER: dict[str, CallableBuilderFromSourceFactory] = {
    "algopy.arc4.arc4_signature": intrinsics.Arc4SignatureBuilder,
    "algopy._util.ensure_budget": ensure_budget.EnsureBudgetBuilder,
    "algopy._util.log": log.LogBuilder,
    "algopy._util.size_of": size_of.SizeOfBuilder,
    "algopy.arc4.emit": arc4.EmitBuilder,
    "algopy.itxn.submit_txns": transaction.SubmitInnerTransactionExpressionBuilder,
    "algopy._compiled.compile_contract": compiled.CompileContractFunctionBuilder,
    "algopy._compiled.compile_logicsig": compiled.CompileLogicSigFunctionBuilder,
    "algopy.arc4.arc4_create": arc4.ARC4CreateFunctionBuilder,
    "algopy.arc4.arc4_update": arc4.ARC4UpdateFunctionBuilder,
    constants.CLS_ARC4_ABI_CALL: arc4.ABICallGenericTypeBuilder,
    "algopy._template_variables.TemplateVar": (
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
    pytypes.NoneType: none.NoneTypeBuilder,
    pytypes.BoolType: bool_.BoolTypeBuilder,
    pytypes.GenericTupleType: tuple_.GenericTupleTypeBuilder,
    pytypes.reversedGenericType: unsigned_builtins.ReversedFunctionExpressionBuilder,
    pytypes.urangeType: unsigned_builtins.UnsignedRangeBuilder,
    pytypes.uenumerateGenericType: unsigned_builtins.UnsignedEnumerateBuilder,
    pytypes.OpUpFeeSourceType: uint64_enums.OpUpFeeSourceTypeBuilder,
    pytypes.GenericBoxType: storage.BoxGenericTypeExpressionBuilder,
    pytypes.BoxRefType: storage.BoxRefTypeBuilder,
    pytypes.GenericBoxMapType: storage.BoxMapGenericTypeExpressionBuilder,
    pytypes.GenericLocalStateType: storage.LocalStateGenericTypeBuilder,
    pytypes.GenericGlobalStateType: storage.GlobalStateGenericTypeBuilder,
    pytypes.ARC4AddressType: arc4.AddressTypeBuilder,
    pytypes.ARC4BoolType: arc4.ARC4BoolTypeBuilder,
    pytypes.ARC4ByteType: functools.partial(arc4.UIntNTypeBuilder, pytypes.ARC4ByteType),
    pytypes.GenericARC4DynamicArrayType: arc4.DynamicArrayGenericTypeBuilder,
    pytypes.GenericARC4StaticArrayType: arc4.StaticArrayGenericTypeBuilder,
    pytypes.ARC4StringType: arc4.ARC4StringTypeBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleGenericTypeBuilder,
    pytypes.ARC4DynamicBytesType: arc4.DynamicBytesTypeBuilder,
    pytypes.AccountType: account.AccountTypeBuilder,
    pytypes.GenericArrayType: array.ArrayGenericTypeBuilder,
    pytypes.GenericImmutableArrayType: immutable_array.ImmutableArrayGenericTypeBuilder,
    pytypes.AssetType: asset.AssetTypeBuilder,
    pytypes.ApplicationType: application.ApplicationTypeBuilder,
    pytypes.BigUIntType: biguint.BigUIntTypeBuilder,
    pytypes.BytesType: bytes_.BytesTypeBuilder,
    pytypes.StringType: string.StringTypeBuilder,
    pytypes.UInt64Type: uint64.UInt64TypeBuilder,
    pytypes.TransactionTypeType: uint64_enums.TransactionTypeTypeBuilder,
    pytypes.OnCompleteActionType: uint64_enums.OnCompletionActionTypeBuilder,
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
    pytypes.uenumerateGenericType: (
        # TODO: fixme, should accept type
        lambda _, loc: unsigned_builtins.UnsignedEnumerateBuilder(loc)
    ),
    pytypes.reversedGenericType: (
        # TODO: fixme, should accept type
        lambda _, loc: unsigned_builtins.ReversedFunctionExpressionBuilder(loc)
    ),
    pytypes.GenericTemplateVarType: template_variables.TemplateVariableExpressionBuilder,
    pytypes.GenericABICallWithReturnType: arc4.ABICallTypeBuilder,
    pytypes.GenericLocalStateType: storage.LocalStateTypeBuilder,
    pytypes.GenericGlobalStateType: storage.GlobalStateTypeBuilder,
    pytypes.GenericBoxType: storage.BoxTypeBuilder,
    pytypes.GenericBoxMapType: storage.BoxMapTypeBuilder,
    pytypes.GenericARC4TupleType: arc4.ARC4TupleTypeBuilder,
    pytypes.GenericTupleType: tuple_.TupleTypeBuilder,
    pytypes.GenericArrayType: array.ArrayTypeBuilder,
    pytypes.GenericImmutableArrayType: immutable_array.ImmutableArrayTypeBuilder,
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
    pytypes.NamedTupleBaseType: tuple_.NamedTupleTypeBuilder,
}

PYTYPE_TO_BUILDER: dict[pytypes.PyType, Callable[[Expression], InstanceBuilder]] = {
    pytypes.ARC4BoolType: arc4.ARC4BoolExpressionBuilder,
    pytypes.ARC4StringType: arc4.ARC4StringExpressionBuilder,
    pytypes.ARC4DynamicBytesType: arc4.DynamicBytesExpressionBuilder,
    pytypes.ARC4ByteType: functools.partial(arc4.UIntNExpressionBuilder, typ=pytypes.ARC4ByteType),
    pytypes.ARC4AddressType: arc4.AddressExpressionBuilder,
    pytypes.AccountType: account.AccountExpressionBuilder,
    pytypes.ApplicationType: application.ApplicationExpressionBuilder,
    pytypes.AssetType: asset.AssetExpressionBuilder,
    pytypes.BigUIntType: biguint.BigUIntExpressionBuilder,
    pytypes.BoolType: bool_.BoolExpressionBuilder,
    pytypes.BytesType: bytes_.BytesExpressionBuilder,
    pytypes.CompiledContractType: compiled.CompiledContractExpressionBuilder,
    pytypes.CompiledLogicSigType: compiled.CompiledLogicSigExpressionBuilder,
    pytypes.StringType: string.StringExpressionBuilder,
    pytypes.UInt64Type: uint64.UInt64ExpressionBuilder,
    pytypes.NoneType: none.NoneExpressionBuilder,
    pytypes.NeverType: none.NoneExpressionBuilder,  # we treat Never as None/void synonym for now
    pytypes.BoxRefType: storage.BoxRefProxyExpressionBuilder,
    # bound
    **{
        uint64_enum_typ: functools.partial(
            uint64.UInt64ExpressionBuilder, enum_type=uint64_enum_typ
        )
        for uint64_enum_typ in (
            pytypes.OpUpFeeSourceType,
            pytypes.TransactionTypeType,
            pytypes.OnCompleteActionType,
        )
    },
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
            transaction.InnerTxnParamsExpressionBuilder, itxn_fieldset_pytyp
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
    pytypes.GenericImmutableArrayType: immutable_array.ImmutableArrayExpressionBuilder,
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
    pytypes.NamedTupleBaseType: tuple_.TupleExpressionBuilder,
}


def builder_for_instance(pytyp: pytypes.PyType, expr: Expression) -> InstanceBuilder:
    if eb := PYTYPE_TO_BUILDER.get(pytyp):
        return eb(expr)
    if eb_param_generic := PYTYPE_GENERIC_TO_BUILDER.get(pytyp.generic):
        return eb_param_generic(expr, pytyp)
    for base in pytyp.mro:
        if eb_base := PYTYPE_BASE_TO_BUILDER.get(base):
            return eb_base(expr, pytyp)
    if isinstance(pytyp, pytypes.UnionType):
        raise CodeError("type unions are unsupported at this location", expr.source_location)
    raise InternalError(f"no builder for instance: {pytyp}", expr.source_location)


def builder_for_type(pytyp: pytypes.PyType, expr_loc: SourceLocation) -> CallableBuilder:
    if tb := PYTYPE_TO_TYPE_BUILDER.get(pytyp):
        return tb(expr_loc)
    if tb_param_generic := PYTYPE_GENERIC_TO_TYPE_BUILDER.get(pytyp.generic):
        return tb_param_generic(pytyp, expr_loc)
    for base in pytyp.mro:
        if tb_base := PYTYPE_BASE_TO_TYPE_BUILDER.get(base):
            return tb_base(pytyp, expr_loc)
    if isinstance(pytyp, pytypes.UnionType):
        raise CodeError("type unions are unsupported at this location", expr_loc)
    raise InternalError(f"no builder for type: {pytyp}", expr_loc)
