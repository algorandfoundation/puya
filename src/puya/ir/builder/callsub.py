from collections.abc import Sequence

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError
from puya.ir.builder._tuple_util import build_tuple_item_names
from puya.ir.builder._utils import assign_targets, new_register_version
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import InvokeSubroutine, Register, Subroutine, Value, ValueProvider, ValueTuple
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def visit_subroutine_call_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.SubroutineCallExpression
) -> ValueProvider | None:
    target = context.resolve_subroutine(expr.target, expr.source_location)
    return _call_subroutine(context, target, expr.args, expr.source_location)


def visit_puya_lib_call_expression(
    context: IRFunctionBuildContext, call: awst_nodes.PuyaLibCall
) -> ValueProvider | None:
    try:
        target = context.embedded_funcs_lookup[call.func.value.id]
    except KeyError:
        raise CodeError(f"invalid puya_lib {call.func.name}", call.source_location) from None
    return _call_subroutine(context, target, call.args, call.source_location)


def _call_subroutine(
    context: IRFunctionBuildContext,
    target: Subroutine,
    args: Sequence[awst_nodes.CallArg],
    call_location: SourceLocation,
) -> ValueProvider | None:
    arg_lookup = _build_arg_lookup(context, args, call_location)

    resolved_args = []
    implicit_args = []
    for idx, param in enumerate(target.parameters):
        arg_val = arg_lookup.get(index=idx, param_name=param.name)
        resolved_args.append(arg_val)
        if param.implicit_return:
            if arg_val in implicit_args:
                logger.error(
                    "mutable values cannot be passed more than once to a subroutine",
                    location=arg_val.source_location,
                )
            implicit_args.append(arg_val)
    if not arg_lookup.is_empty:
        raise CodeError("function call arguments do not match signature", call_location) from None
    invoke_expr = InvokeSubroutine(
        source_location=call_location, args=resolved_args, target=target
    )
    if not implicit_args:
        return invoke_expr

    return_values = context.visitor.materialise_value_provider(invoke_expr, target.short_name)
    while implicit_args:
        in_arg = implicit_args.pop()
        out_value = return_values.pop()
        if isinstance(in_arg, Register):
            out_arg = new_register_version(context, in_arg)
            assign_targets(
                context,
                source=out_value,
                targets=[out_arg],
                assignment_location=call_location,
            )

    return (
        ValueTuple(values=return_values, source_location=call_location) if return_values else None
    )


@attrs.define
class _ArgLookup:
    _source_location: SourceLocation
    _positional_args: dict[int, Value] = attrs.field(factory=dict, init=False)
    _named_args: dict[str, Value] = attrs.field(factory=dict, init=False)
    _arg_idx: int = attrs.field(default=0, init=False)

    @property
    def is_empty(self) -> bool:
        return not self._named_args and not self._positional_args

    def add(self, name: str | None, value: Value) -> None:
        if name is None:
            self._positional_args[self._arg_idx] = value
        else:
            self._named_args[name] = value
        self._arg_idx += 1

    def get(self, index: int, param_name: str | None) -> Value:
        if param_name is not None:
            by_name = self._named_args.pop(param_name, None)
            if by_name is not None:
                return by_name
        try:
            return self._positional_args.pop(index)
        except KeyError:
            raise CodeError(
                "function call arguments do not match signature", self._source_location
            ) from None


def _build_arg_lookup(
    context: IRFunctionBuildContext,
    args: Sequence[awst_nodes.CallArg],
    call_location: SourceLocation,
) -> _ArgLookup:
    lookup = _ArgLookup(call_location)
    for expr_arg in args:
        if not isinstance(expr_arg.value.wtype, wtypes.WTuple):
            value = context.visitor.visit_and_materialise_single(expr_arg.value)
            lookup.add(name=expr_arg.name, value=value)
        else:
            values = context.visitor.visit_and_materialise(expr_arg.value)
            if expr_arg.name is None:
                for tup_value in values:
                    lookup.add(name=None, value=tup_value)
            else:
                item_names = build_tuple_item_names(
                    base_name=expr_arg.name,
                    wtype=expr_arg.value.wtype,
                    source_location=call_location,
                )
                for tup_value, (tup_item_name, _) in zip(values, item_names, strict=True):
                    lookup.add(name=tup_item_name, value=tup_value)

    return lookup
