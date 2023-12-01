from wyvern.awst import wtypes
from wyvern.awst.nodes import Expression
from wyvern.awst_build.eb.base import ExpressionBuilder
from wyvern.errors import TodoError


def var_expression(expr: Expression) -> ExpressionBuilder:
    # To avoid circular imports
    from wyvern.awst_build.eb.abi import (
        DynamicArrayExpressionBuilder,
        StaticArrayExpressionBuilder,
        StringExpressionBuilder,
        UIntNExpressionBuilder,
    )
    from wyvern.awst_build.eb.address import AddressExpressionBuilder
    from wyvern.awst_build.eb.array import ArrayExpressionBuilder
    from wyvern.awst_build.eb.asset import AssetExpressionBuilder
    from wyvern.awst_build.eb.biguint import BigUIntExpressionBuilder
    from wyvern.awst_build.eb.bool import BoolExpressionBuilder
    from wyvern.awst_build.eb.bytes import BytesExpressionBuilder
    from wyvern.awst_build.eb.struct import StructExpressionBuilder
    from wyvern.awst_build.eb.tuple import TupleExpressionBuilder
    from wyvern.awst_build.eb.uint64 import UInt64ExpressionBuilder
    from wyvern.awst_build.eb.void import VoidExpressionBuilder

    match expr.wtype:
        case wtypes.address_wtype:
            return AddressExpressionBuilder(expr)
        case wtypes.asset_wtype:
            return AssetExpressionBuilder(expr)
        case wtypes.biguint_wtype:
            return BigUIntExpressionBuilder(expr)
        case wtypes.bytes_wtype:
            return BytesExpressionBuilder(expr)
        case wtypes.uint64_wtype:
            return UInt64ExpressionBuilder(expr)
        case wtypes.bool_wtype:
            return BoolExpressionBuilder(expr)
        case wtypes.void_wtype:
            return VoidExpressionBuilder(expr)
        case wtypes.WArray():
            return ArrayExpressionBuilder(expr)
        case wtypes.WStructType():
            return StructExpressionBuilder(expr)
        case wtypes.WTuple():
            return TupleExpressionBuilder(expr)
        case wtypes.abi_string_wtype:
            return StringExpressionBuilder(expr)
        case wtypes.AbiUIntN():
            return UIntNExpressionBuilder(expr)
        case wtypes.AbiDynamicArray():
            return DynamicArrayExpressionBuilder(expr)
        case wtypes.AbiStaticArray():
            return StaticArrayExpressionBuilder(expr)
        case _:
            raise TodoError(
                expr.source_location, f"need to add var builder for wtype {expr.wtype}"
            )
