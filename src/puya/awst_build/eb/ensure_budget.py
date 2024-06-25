import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    CallArg,
    Expression,
    FreeSubroutineTarget,
    IntegerConstant,
    SubroutineCallExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.none import NoneExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class EnsureBudgetBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        required_budget_arg_name = "required_budget"
        fee_source_arg_name = "fee_source"
        arg_mapping, _ = get_arg_mapping(
            required_positional_names=[required_budget_arg_name],
            optional_positional_names=[fee_source_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        required_budget_arg = arg_mapping.get(required_budget_arg_name)
        if required_budget_arg is None:
            required_budget = dummy_value(pytypes.UInt64Type, location)
        else:
            required_budget = expect.argument_of_type_else_dummy(
                required_budget_arg, pytypes.UInt64Type, resolve_literal=True
            )

        fee_source_arg = arg_mapping.get(fee_source_arg_name)
        if fee_source_arg is None:
            fee_source_expr: Expression = UInt64Constant(value=0, source_location=location)
        else:
            fee_source_expr = expect.argument_of_type_else_dummy(
                fee_source_arg, pytypes.UInt64Type
            ).resolve()
        if (
            isinstance(fee_source_expr, IntegerConstant)
            and fee_source_expr.value not in FeeSourceValues.values()
        ):
            logger.error("invalid argument value", location=fee_source_expr.source_location)

        call_args = [
            CallArg(
                name=required_budget_arg_name,
                value=required_budget.resolve(),
            ),
            CallArg(
                name=fee_source_arg_name,
                value=fee_source_expr,
            ),
        ]
        call_expr = SubroutineCallExpression(
            source_location=location,
            target=FreeSubroutineTarget(module_name="algopy", name="ensure_budget"),
            args=call_args,
            wtype=wtypes.void_wtype,
        )
        return NoneExpressionBuilder(call_expr)


FeeSourceValues = {
    "GroupCredit": 0,
    "AppAccount": 1,
    "Any": 2,
}


class OpUpFeeSourceTypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.UInt64Type, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate enumeration type", location)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        if (value := FeeSourceValues.get(name)) is None:
            return super().member_access(name, expr, location)
        const_expr = UInt64Constant(value=value, source_location=location)
        return UInt64ExpressionBuilder(const_expr)
