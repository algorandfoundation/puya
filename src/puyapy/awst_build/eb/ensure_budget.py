import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import (
    CallArg,
    Expression,
    PuyaLibCall,
    PuyaLibFunction,
    UInt64Constant,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class EnsureBudgetBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
                fee_source_arg, pytypes.OpUpFeeSourceType
            ).resolve()

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
        call_expr = PuyaLibCall(
            func=PuyaLibFunction.ensure_budget,
            args=call_args,
            source_location=location,
        )
        return NoneExpressionBuilder(call_expr)
