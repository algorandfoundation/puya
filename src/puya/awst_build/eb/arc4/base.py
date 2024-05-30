from __future__ import annotations

import abc
import typing

import typing_extensions

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
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
from puya.awst_build.eb._utils import get_bytes_expr
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    FunctionBuilder,
    InstanceBuilder,
    InstanceExpressionBuilder,
    NodeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class ARC4ClassExpressionBuilder(BytesBackedClassExpressionBuilder[_TPyType_co], abc.ABC):
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "from_log":
                return ARC4FromLogBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


class ARC4FromLogBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location=location)
        self.typ = typ

    @classmethod
    def abi_expr_from_log(
        cls, typ: pytypes.PyType, value: Expression, location: SourceLocation
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
            expr=checked_arc4_value,
            wtype=typ.wtype,
            source_location=location,
        )

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case [NodeBuilder() as eb]:
                result_expr = self.abi_expr_from_log(self.typ, eb.rvalue(), location)
                return builder_for_instance(self.typ, result_expr)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class CopyBuilder(FunctionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation, typ: pytypes.PyType):
        self._typ = typ
        super().__init__(location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case []:
                expr_result = Copy(
                    value=self.expr, wtype=self.expr.wtype, source_location=location
                )
                return builder_for_instance(self._typ, expr_result)
        raise CodeError("Invalid/Unexpected arguments", location)


def arc4_compare_bytes(
    lhs: InstanceExpressionBuilder,
    op: BuilderComparisonOp,
    rhs: NodeBuilder | Literal,
    location: SourceLocation,
) -> InstanceBuilder:
    if isinstance(rhs, Literal):
        raise CodeError(
            f"Cannot compare arc4 encoded value of {lhs.pytype} to a literal value", location
        )
    if rhs.pytype != lhs.pytype:
        return NotImplemented
    cmp_expr = BytesComparisonExpression(
        source_location=location,
        lhs=get_bytes_expr(lhs.expr),
        operator=EqualityComparison(op.value),
        rhs=get_bytes_expr(rhs.rvalue()),
    )
    return BoolExpressionBuilder(cmp_expr)


def arc4_bool_bytes(
    expr: Expression, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> InstanceBuilder:
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
