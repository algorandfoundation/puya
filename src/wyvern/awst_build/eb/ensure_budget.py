from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes

from wyvern.awst import wtypes
from wyvern.awst.nodes import (
    CallArg,
    FreeSubroutineTarget,
    Literal,
    SubroutineCallExpression,
)
from wyvern.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from wyvern.parse import SourceLocation


class EnsureBudgetBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        call_args: Sequence[CallArg]
        match args:
            case [_required_budget, _fee_source]:
                call_args = []
            case [_required_budget]:
                call_args = []
            case _:
                raise CodeError("Incorrect args", location)

        call_expr = SubroutineCallExpression(
            source_location=location,
            target=FreeSubroutineTarget(module_name="algopy", name="ensure_budget"),
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
