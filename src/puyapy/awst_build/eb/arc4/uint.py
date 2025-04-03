import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    BigUIntConstant,
    Expression,
    IntegerConstant,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb.arc4._base import ARC4TypeBuilder
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)

__all__ = [
    "UIntNTypeBuilder",
    "UIntNExpressionBuilder",
]

logger = log.get_logger(__name__)


class UIntNTypeBuilder(ARC4TypeBuilder[pytypes.ARC4UIntNType]):
    def __init__(self, pytype: pytypes.PyType, location: SourceLocation):
        assert isinstance(pytype, pytypes.ARC4UIntNType)
        super().__init__(pytype, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        pytype = self.produces()
        match literal.value:
            case int(int_value):
                if int_value < 0 or int_value.bit_length() > pytype.bits:
                    logger.error(f"invalid {pytype} value", location=literal.source_location)
                # take int() of the value since it could match a bool also
                expr = IntegerConstant(
                    value=int(int_value), wtype=pytype.wtype, source_location=location
                )
                return UIntNExpressionBuilder(expr, pytype)
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
        typ = self.produces()
        wtype = typ.wtype
        match arg:
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                return arg.resolve_literal(UIntNTypeBuilder(typ, location))
            case None:
                expr: Expression = IntegerConstant(value=0, wtype=wtype, source_location=location)
            case _:
                encodeable = expect.argument_of_type_else_dummy(
                    arg, pytypes.UInt64Type, pytypes.BigUIntType, pytypes.BoolType
                )
                expr = ARC4Encode(
                    value=encodeable.resolve(), wtype=wtype, source_location=location
                )
        return UIntNExpressionBuilder(expr, typ)


class UIntNExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.ARC4UIntNType],
    BytesBackedInstanceExpressionBuilder[pytypes.ARC4UIntNType],
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UIntNType)
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                result_expr = ARC4Decode(
                    value=self.resolve(),
                    wtype=self.pytype.native_type.wtype,
                    source_location=location,
                )
                return builder_for_instance(self.pytype.native_type, result_expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        cmp_expr = NumericComparisonExpression(
            operator=NumericComparison.eq if negate else NumericComparison.ne,
            lhs=self._as_biguint(),
            rhs=BigUIntConstant(value=0, source_location=location),
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(UIntNTypeBuilder(self.pytype, other.source_location))
        if pytypes.BigUIntType <= other.pytype:
            other_expr = other.resolve()
        elif other.pytype.is_type_or_subtype(pytypes.BoolType, pytypes.UInt64Type):
            other_expr = intrinsic_factory.itob_as(other.resolve(), wtypes.biguint_wtype, location)
        elif isinstance(other.pytype, pytypes.ARC4UIntNType):
            other_expr = ReinterpretCast(
                expr=other.resolve(),
                wtype=wtypes.biguint_wtype,
                source_location=other.source_location,
            )
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            operator=NumericComparison(op.value),
            lhs=self._as_biguint(),
            rhs=other_expr,
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)

    def _as_biguint(self) -> Expression:
        return ReinterpretCast(
            expr=self.resolve(),
            wtype=wtypes.biguint_wtype,
            source_location=self.source_location,
        )
