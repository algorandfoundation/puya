from __future__ import annotations

import abc
import typing

import typing_extensions

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
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
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._utils import get_bytes_expr, get_bytes_expr_builder
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance, var_expression
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


_TARC4Type = typing_extensions.TypeVar(
    "_TARC4Type", bound=wtypes.ARC4Type, default=wtypes.ARC4Type
)


class ARC4ClassExpressionBuilder(BytesBackedClassExpressionBuilder[_TARC4Type], abc.ABC):
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
                wtype=wtypes.WTuple((arc4_value.wtype, wtypes.bool_wtype), location),
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
        arg_typs: Sequence[pytypes.PyType],
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
    def __init__(
        self, expr: Expression, location: SourceLocation, typ: pytypes.PyType | None = None
    ):  # TODO
        self._typ = typ
        super().__init__(location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                expr_result = Copy(
                    value=self.expr, wtype=self.expr.wtype, source_location=location
                )
                if self._typ is None:
                    return var_expression(expr_result)
                return builder_for_instance(self._typ, expr_result)
        raise CodeError("Invalid/Unexpected arguments", location)


class ARC4EncodedExpressionBuilder(ValueExpressionBuilder, abc.ABC):
    def __init__(
        self,
        expr: Expression,
        native_wtype: wtypes.WType | None,
        native_pytype: pytypes.PyType | None,
    ):
        super().__init__(expr)
        self._native_pytype = native_pytype
        self._native_wtype = native_wtype

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "native" if self._native_pytype is not None:
                result_expr: Expression = ARC4Decode(
                    value=self.expr,
                    wtype=self._native_pytype.wtype,
                    source_location=location,
                )
                return builder_for_instance(self._native_pytype, result_expr)
            case "native" if self._native_wtype is not None:
                result_expr = ARC4Decode(
                    value=self.expr,
                    wtype=self._native_wtype,
                    source_location=location,
                )
                return var_expression(result_expr)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                raise CodeError(f"Unrecognised member of bytes: {name}", location)

    @typing.override
    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return arc4_compare_bytes(self, op, other, location)

    @typing.override
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
    return BoolExpressionBuilder(cmp_expr)


def arc4_bool_bytes(
    expr: Expression, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> ExpressionBuilder:
    return BoolExpressionBuilder(
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
