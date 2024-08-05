from collections.abc import Sequence

import attrs

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir.builder._utils import assign_targets, new_register_version
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import InvokeSubroutine, Register, Value, ValueProvider, ValueTuple
from puya.ir.utils import format_tuple_index


def visit_subroutine_call_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.SubroutineCallExpression
) -> ValueProvider | None:
    sref = context.resolve_function_reference(expr.target, expr.source_location)
    target = context.subroutines[sref]

    arg_lookup = _build_arg_lookup(context, expr.args)

    resolved_args = []
    implicit_args = []
    for idx, param in enumerate(target.parameters):
        arg_val = arg_lookup.get(index=idx, name=param.name)
        resolved_args.append(arg_val)
        if param.implicit_return:
            implicit_args.append(arg_val)

    invoke_expr = InvokeSubroutine(
        source_location=expr.source_location, args=resolved_args, target=target
    )
    if not implicit_args:
        return invoke_expr

    return_values = context.visitor.materialise_value_provider(invoke_expr, target.method_name)
    while implicit_args:
        in_arg = implicit_args.pop()
        out_value = return_values.pop()
        if isinstance(in_arg, Register):
            out_arg = new_register_version(context, in_arg)
            assign_targets(
                context,
                source=out_value,
                targets=[out_arg],
                assignment_location=expr.source_location,
            )

    return (
        ValueTuple(values=return_values, source_location=expr.source_location)
        if return_values
        else None
    )


@attrs.define
class _ArgLookup:
    _positional_args: dict[int, Value] = attrs.field(factory=dict, init=False)
    _named_args: dict[str, Value] = attrs.field(factory=dict, init=False)
    _arg_idx: int = attrs.field(default=0, init=False)

    def add(self, name: str | None, value: Value) -> None:
        if name is None:
            self._positional_args[self._arg_idx] = value
        else:
            self._named_args[name] = value
        self._arg_idx += 1

    def get(self, index: int, name: str | None) -> Value:
        if name is not None:
            by_name = self._named_args.get(name)
            if by_name is not None:
                return by_name
        return self._positional_args[index]


def _build_arg_lookup(
    context: IRFunctionBuildContext, args: Sequence[awst_nodes.CallArg]
) -> _ArgLookup:
    lookup = _ArgLookup()
    for expr_arg in args:
        if not isinstance(expr_arg.value.wtype, wtypes.WTuple):
            value = context.visitor.visit_and_materialise_single(expr_arg.value)
            lookup.add(name=expr_arg.name, value=value)
        else:
            values = context.visitor.visit_and_materialise(expr_arg.value)
            for tup_idx, tup_value in enumerate(values):
                if expr_arg.name is None:
                    tup_item_name = None
                else:
                    tup_item_name = format_tuple_index(expr_arg.name, tup_idx)
                lookup.add(name=tup_item_name, value=tup_value)
    return lookup
