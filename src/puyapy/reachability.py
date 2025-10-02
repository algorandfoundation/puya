import ast
import enum
import operator
import typing
from collections.abc import Callable, Iterable, Mapping
from functools import cached_property
from pathlib import Path


@enum.unique
class ConditionValue(enum.Enum):
    UNKNOWN = enum.auto()
    ALWAYS_TRUE = enum.auto()
    ALWAYS_FALSE = enum.auto()
    TYPE_CHECKING_TRUE = enum.auto()
    TYPE_CHECKING_FALSE = enum.auto()

    @cached_property
    def negated(self) -> "ConditionValue":
        match self:
            case ConditionValue.UNKNOWN:
                return TRUTH_VALUE_UNKNOWN
            case ConditionValue.ALWAYS_TRUE:
                return ALWAYS_FALSE
            case ConditionValue.ALWAYS_FALSE:
                return ALWAYS_TRUE
            case ConditionValue.TYPE_CHECKING_TRUE:
                return TYPE_CHECKING_FALSE
            case ConditionValue.TYPE_CHECKING_FALSE:
                return TYPE_CHECKING_TRUE


TRUTH_VALUE_UNKNOWN: typing.Final = ConditionValue.UNKNOWN
ALWAYS_TRUE: typing.Final = ConditionValue.ALWAYS_TRUE
ALWAYS_FALSE: typing.Final = ConditionValue.ALWAYS_FALSE
TYPE_CHECKING_TRUE: typing.Final = ConditionValue.TYPE_CHECKING_TRUE
TYPE_CHECKING_FALSE: typing.Final = ConditionValue.TYPE_CHECKING_FALSE


def combine_conditions(conditions: Iterable[ConditionValue]) -> ConditionValue:
    results = set(conditions)
    if not results:
        return ALWAYS_TRUE
    if len(results) == 1:
        return results.pop()
    if ALWAYS_FALSE in results:
        return ALWAYS_FALSE
    elif TYPE_CHECKING_FALSE in results:
        return TYPE_CHECKING_FALSE
    elif results <= {ALWAYS_TRUE, TYPE_CHECKING_TRUE}:
        return TYPE_CHECKING_TRUE
    else:
        return TRUTH_VALUE_UNKNOWN


def infer_condition_value(expr: ast.expr, file: Path) -> ConditionValue:
    match expr:
        case ast.Constant(value):
            if value:
                return ALWAYS_TRUE
            else:
                return ALWAYS_FALSE
        case ast.Attribute(_, "TYPE_CHECKING", ast.Load()):
            return TYPE_CHECKING_TRUE
        case ast.Name("TYPE_CHECKING", ast.Load()):
            return TYPE_CHECKING_TRUE
        case ast.UnaryOp(ast.Not(), operand):
            nested = infer_condition_value(operand, file)
            return nested.negated
        case ast.BoolOp(ast.Or(), operands):
            results = {infer_condition_value(operand, file) for operand in operands}
            if len(results) == 1:
                return results.pop()
            if ALWAYS_TRUE in results:
                return ALWAYS_TRUE
            elif TYPE_CHECKING_TRUE in results:
                return TYPE_CHECKING_TRUE
            elif results <= {ALWAYS_FALSE, TYPE_CHECKING_FALSE}:
                return ALWAYS_FALSE
            else:
                return TRUTH_VALUE_UNKNOWN
        case ast.BoolOp(ast.And(), operands):
            results = {infer_condition_value(operand, file) for operand in operands}
            return combine_conditions(results)
        # TODO: ?
        # case ast.BinOp(left=ast.Constant(left), op=bin_op, right=ast.Constant(right)):
        #     try:
        #         op_impl = _AST_BIN_OP_TO_OP[type(op)]
        #     except KeyError:
        #         raise InternalError(
        #             f"unknown operator: {op}", _ast_source_location(expr, file)
        #         ) from None
        #     try:
        #         result = op_impl(left, right)
        #     except Exception:
        #         logger.error()
        #         return None
        #     else:
        #         return None
        # TODO: ast.Compare ?
        case _:
            return TRUTH_VALUE_UNKNOWN


_AST_BIN_OP_TO_OP: Mapping[type[ast.operator], Callable] = {  # type: ignore[type-arg]
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_,
    ast.MatMult: operator.matmul,
}

_AST_CMP_TO_OP: Mapping[type[ast.cmpop], Callable] = {  # type: ignore[type-arg]
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}
