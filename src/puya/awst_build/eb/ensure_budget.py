from __future__ import annotations

import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    CallArg,
    FreeSubroutineTarget,
    Literal,
    SubroutineCallExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder, TypeBuilder
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import expect_operand_type, get_arg_mapping
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class EnsureBudgetBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
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
                value=expect_operand_type(required_budget, pytypes.UInt64Type).rvalue(),
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
                fee_source_expr = UInt64Constant(value=0, source_location=location)
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
            target=FreeSubroutineTarget(module_name="algopy", name="ensure_budget"),
            args=call_args,
            wtype=wtypes.void_wtype,
        )
        return VoidExpressionBuilder(call_expr)


class OpUpFeeSourceClassBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.UInt64Type, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("Cannot instantiate enumeration type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "GroupCredit":
                return Literal(value=0, source_location=location)
            case "AppAccount":
                return Literal(value=1, source_location=location)
            case "Any":
                return Literal(value=2, source_location=location)
            case _:
                return super().member_access(name, location)
