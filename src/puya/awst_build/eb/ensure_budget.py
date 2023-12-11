from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    CallArg,
    FreeSubroutineTarget,
    Literal,
    SubroutineCallExpression,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype, get_arg_mapping
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class EnsureBudgetBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        required_budget_arg_name = "required_budget"
        fee_source_arg_name = "fee_source"
        arg_mapping = get_arg_mapping(
            positional_arg_names=[required_budget_arg_name, fee_source_arg_name],
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        try:
            required_budget = arg_mapping.pop(required_budget_arg_name)
        except KeyError:
            raise CodeError(
                f"Missing required argument '{required_budget_arg_name}'", location
            ) from None

        call_args = [
            CallArg(
                name=required_budget_arg_name,
                value=expect_operand_wtype(required_budget, wtypes.uint64_wtype),
            )
        ]

        match arg_mapping.pop(fee_source_arg_name, None):
            case Literal(
                value=int(fee_source_value), source_location=fee_source_loc
            ) if 0 <= fee_source_value <= 2:
                fee_source_expr = UInt64Constant(
                    value=fee_source_value, source_location=fee_source_loc
                )
            case None:
                fee_source_expr = UInt64Constant(value=2, source_location=location)
            case _:
                raise CodeError(f"Invalid argument value for {fee_source_arg_name}", location)
        call_args.append(
            CallArg(
                name=fee_source_arg_name,
                value=fee_source_expr,
            )
        )
        if arg_mapping:
            raise CodeError(f"Unexpected arguments: {', '.join(arg_mapping)}", location)
        call_expr = SubroutineCallExpression(
            source_location=location,
            target=FreeSubroutineTarget(module_name="puyapy", name="ensure_budget"),
            args=call_args,
            wtype=wtypes.void_wtype,
        )
        return var_expression(call_expr)


class OpUpFeeSourceClassBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.uint64_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "GroupCredit":
                return Literal(value=0, source_location=location)
            case "AppAccount":
                return Literal(value=1, source_location=location)
            case "Any":
                return Literal(value=2, source_location=location)
            case _:
                return super().member_access(name, location)
