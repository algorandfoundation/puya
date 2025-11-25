import ast
import enum
import typing
from functools import cached_property

from puyapy.fast import nodes as fast_nodes


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


def infer_condition_value(expr: fast_nodes.Expression) -> ConditionValue:
    match expr:
        case fast_nodes.Constant(value=value):
            if value:
                return ALWAYS_TRUE
            else:
                return ALWAYS_FALSE
        # TODO: these next two cases are hacks,which other type checkers also employ, but
        #       maybe we can do without it here if we keep track of imports of/from typing and
        #       don't allow importing typing/TYPE_CHECKING from another module? a false negative
        #       seems preferable to a false positive?
        case fast_nodes.Attribute(attr="TYPE_CHECKING", ctx=ast.Load()):
            return TYPE_CHECKING_TRUE
        case fast_nodes.Name(id="TYPE_CHECKING", ctx=ast.Load()):
            return TYPE_CHECKING_TRUE
        case fast_nodes.UnaryOp(op=ast.Not(), operand=operand):
            nested = infer_condition_value(operand)
            return nested.negated
        case fast_nodes.BoolOp(op=ast.Or(), values=operands):
            results = {infer_condition_value(operand) for operand in operands}
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
        case fast_nodes.BoolOp(op=ast.And(), values=operands):
            results = {infer_condition_value(operand) for operand in operands}
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
        case _:
            return TRUTH_VALUE_UNKNOWN
