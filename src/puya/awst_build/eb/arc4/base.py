from __future__ import annotations

import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    BytesComparisonExpression,
    BytesConstant,
    BytesEncoding,
    CheckedMaybe,
    Copy,
    EqualityComparison,
    Expression,
    Literal,
    ReinterpretCast,
    SingleEvaluation,
    TupleExpression,
)
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def get_bytes_expr(expr: Expression) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=expr.source_location
    )


def get_bytes_expr_builder(expr: Expression) -> ExpressionBuilder:
    return var_expression(get_bytes_expr(expr))


class ARC4ClassExpressionBuilder(BytesBackedClassExpressionBuilder, abc.ABC):
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "from_log":
                return ARC4FromLogBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


def get_integer_literal_value(eb_or_literal: ExpressionBuilder | Literal, purpose: str) -> int:
    match eb_or_literal:
        case Literal(value=int(lit_value)):
            return lit_value
        case _:
            raise CodeError(f"{purpose} must be compile time constant")


class ARC4EncodeBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.WType):
        super().__init__(location=location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [
                ExpressionBuilder() as eb
            ] if eb.rvalue().wtype == wtypes.arc4_to_avm_equivalent_wtype(self.wtype):
                value = eb.rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

        return var_expression(
            ARC4Encode(
                source_location=location,
                value=value,
                wtype=self.wtype,
            )
        )


class ARC4FromLogBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.WType):
        super().__init__(location=location)
        self.wtype = wtype

    @classmethod
    def abi_expr_from_log(
        cls, wtype: wtypes.WType, value: Expression, location: SourceLocation
    ) -> Expression:
        tmp_value = SingleEvaluation(value)
        arc4_value = intrinsic_factory.extract(tmp_value, start=4, loc=location)
        arc4_prefix = intrinsic_factory.extract(tmp_value, start=0, length=4, loc=location)
        arc4_prefix_is_valid = BytesComparisonExpression(
            lhs=arc4_prefix,
            rhs=BytesConstant(
                value=b"\x15\x1f\x7c\x75",
                source_location=location,
                encoding=BytesEncoding.base16,
            ),
            operator=EqualityComparison.eq,
            source_location=location,
        )
        checked_arc4_value = CheckedMaybe(
            expr=TupleExpression(
                items=(arc4_value, arc4_prefix_is_valid),
                wtype=wtypes.WTuple.from_types((arc4_value.wtype, wtypes.bool_wtype)),
                source_location=location,
            ),
            comment="ARC4 prefix is valid",
        )
        return ReinterpretCast(
            source_location=location,
            expr=checked_arc4_value,
            wtype=wtype,
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                return var_expression(self.abi_expr_from_log(self.wtype, eb.rvalue(), location))
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class CopyBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location)
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                return var_expression(
                    Copy(value=self.expr, wtype=self.expr.wtype, source_location=location)
                )
        raise CodeError("Invalid/Unexpected arguments", location)


def native_eb(expr: Expression, location: SourceLocation) -> ExpressionBuilder:
    match expr.wtype:
        case wtypes.arc4_string_wtype | wtypes.arc4_dynamic_bytes | wtypes.arc4_bool_wtype:
            pass
        case wtypes.ARC4UIntN() | wtypes.ARC4UFixedNxM() | wtypes.ARC4Tuple():
            pass
        case _:
            raise InternalError("Unsupported wtype for ARC4Decode", location)
    return var_expression(
        ARC4Decode(
            source_location=location,
            value=expr,
            wtype=wtypes.arc4_to_avm_equivalent_wtype(expr.wtype),
        )
    )


class ARC4EncodedExpressionBuilder(ValueExpressionBuilder, abc.ABC):
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "native":
                return native_eb(self.expr, location)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                raise CodeError(f"Unrecognised member of bytes: {name}", location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return arc4_compare_bytes(self, op, other, location)

    @abc.abstractmethod
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        # TODO: lift this up to ValueExpressionBuilder
        raise NotImplementedError


def arc4_compare_bytes(
    lhs: ValueExpressionBuilder,
    op: BuilderComparisonOp,
    rhs: ExpressionBuilder | Literal,
    location: SourceLocation,
) -> ExpressionBuilder:
    if isinstance(rhs, Literal):
        raise CodeError(
            f"Cannot compare arc4 encoded value of {lhs.wtype} to a literal value", location
        )
    other_expr = rhs.rvalue()
    if other_expr.wtype != lhs.wtype:
        return NotImplemented
    cmp_expr = BytesComparisonExpression(
        source_location=location,
        lhs=get_bytes_expr(lhs.expr),
        operator=EqualityComparison(op.value),
        rhs=get_bytes_expr(other_expr),
    )
    return var_expression(cmp_expr)


def arc4_bool_bytes(
    expr: Expression, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> ExpressionBuilder:
    return var_expression(
        BytesComparisonExpression(
            operator=EqualityComparison.eq if negate else EqualityComparison.ne,
            lhs=get_bytes_expr(expr),
            rhs=BytesConstant(
                value=false_bytes,
                encoding=BytesEncoding.base16,
                source_location=location,
            ),
            source_location=location,
        )
    )
