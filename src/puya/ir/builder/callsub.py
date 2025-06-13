from collections import defaultdict
from collections.abc import Iterator, Sequence

import attrs

import puya.ir.models as ir
from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder._utils import assign
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import TupleIRType, sum_wtypes_arity, wtype_to_ir_type
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def visit_subroutine_call_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.SubroutineCallExpression
) -> ir.ValueProvider | None:
    target = context.resolve_subroutine(expr.target, expr.source_location)
    return _call_subroutine(context, target, expr.args, expr.source_location)


def visit_puya_lib_call_expression(
    context: IRFunctionBuildContext, call: awst_nodes.PuyaLibCall
) -> ir.ValueProvider | None:
    try:
        full_name = PuyaLibIR(call.func.value.id)
    except KeyError:
        raise CodeError(f"invalid puya_lib {call.func.name}", call.source_location) from None
    target = context.resolve_embedded_func(full_name)
    return _call_subroutine(context, target, call.args, call.source_location)


def _call_subroutine(
    context: IRFunctionBuildContext,
    target: ir.Subroutine,
    args: Sequence[awst_nodes.CallArg],
    call_location: SourceLocation,
) -> ir.ValueProvider | None:
    # this will materialize in the correct order
    arg_lookup = _ArgLookup(context, args)
    # the IR arguments in the order the invoked subroutine expects them to be passed
    ordered_args = []
    # arguments that are returned from the invoked subroutine automatically
    implicit_return_args = list[str | None]()
    var_name_to_params = defaultdict[str, list[ir.Parameter]](list)
    for idx, param in enumerate(target.parameters):
        try:
            ir_val, maybe_var_name = arg_lookup.pop(index=idx, param_name=param.name)
        except KeyError:
            # parameter doesn't have corresponding argument, this is a double check,
            # front ends should be doing higher level type checking, so error message is general
            return _dummy_return(
                "function call arguments do not match signature", target, call_location
            )
        ordered_args.append(ir_val)
        if maybe_var_name is not None:
            var_name_to_params[maybe_var_name].append(param)

        if param.implicit_return:
            implicit_return_args.append(maybe_var_name)

    if arg_lookup:
        # arguments that didn't match a parameter remaining - again a double check,
        # so error message doesn't need to be too specific
        return _dummy_return(
            "function call arguments do not match signature", target, call_location
        )

    for var_params in var_name_to_params.values():
        # this check handles two cases
        # 1) a variable being passed and implicitly returned more than once - this would require
        #   changes to the way the invoked subroutine handles the args
        # 2) as soon as a "pass-by-reference" variable is passed more than once, there is aliasing.
        #   if there is no possibility of mutations, this has no impact, however if at least
        #   one reference can mutate the value then from the callers perspective there is
        #   an aliasing problem.
        if len(var_params) > 1 and any(p.implicit_return for p in var_params):
            return _dummy_return(
                "mutable values cannot be passed more than once to a subroutine",
                target,
                call_location,
            )

    invoke_expr = ir.InvokeSubroutine(
        target=target, args=ordered_args, source_location=call_location
    )
    if not implicit_return_args:
        return invoke_expr

    invoke_result = context.visitor.materialise_value_provider(invoke_expr, target.short_name)
    num_explicit = len(target.explicit_returns)
    return_values, inout_values = invoke_result[:num_explicit], invoke_result[num_explicit:]

    for maybe_var_name, inout_value in zip(implicit_return_args, inout_values, strict=True):
        if maybe_var_name is not None:
            assign(context, inout_value, name=maybe_var_name, assignment_location=call_location)

    if return_values:
        return ir.ValueTuple(values=return_values, source_location=call_location)
    return None


def _dummy_return(
    error_message: str, target: ir.Subroutine, loc: SourceLocation
) -> ir.ValueProvider | None:
    logger.error(error_message, location=loc)
    match target.explicit_returns:
        case []:
            return None
        case [single_ir_type]:
            return ir.Undefined(ir_type=single_ir_type, source_location=loc)
        case multiple_ir_types:
            values = [ir.Undefined(ir_type=irt, source_location=loc) for irt in multiple_ir_types]
            return ir.ValueTuple(values=values, source_location=loc)


_IRValueWithSourceVar = tuple[ir.Value, str | None]


@attrs.define(init=False)
class _ArgLookup:
    _data: dict[int | str, _IRValueWithSourceVar]

    def __init__(self, context: IRFunctionBuildContext, args: Sequence[awst_nodes.CallArg]):
        # IR args, materialized and expanded for tuples
        ir_args = list[tuple[str | None, ir.Value]]()
        src_var_names = list[str | None]()
        for expr_arg in args:
            awst_value = expr_arg.value
            arg_name = expr_arg.name
            src_var_names.extend(_expand_tuple_vars(awst_value))
            ir_type = wtype_to_ir_type(
                awst_value.wtype, source_location=awst_value.source_location, allow_tuple=True
            )
            if not isinstance(ir_type, TupleIRType):
                value = context.visitor.visit_and_materialise_single(awst_value)
                ir_args.append((arg_name, value))
            else:
                values = context.visitor.visit_and_materialise(awst_value)
                if arg_name is None:
                    ir_args.extend((None, tup_value) for tup_value in values)
                else:
                    item_names = ir_type.build_item_names(arg_name)
                    ir_args.extend(
                        (tup_item_name, tup_value)
                        for tup_value, tup_item_name in zip(values, item_names, strict=True)
                    )

        data = {
            (arg_idx if name is None else name): (value, src_var)
            for arg_idx, ((name, value), src_var) in enumerate(
                zip(ir_args, src_var_names, strict=True)
            )
        }
        self.__attrs_init__(data=data)

    def __bool__(self) -> bool:
        return bool(self._data)

    def pop(self, index: int, param_name: str | None) -> _IRValueWithSourceVar:
        if param_name in self._data:
            return self._data.pop(param_name)
        return self._data.pop(index)


def _expand_tuple_vars(expr: awst_nodes.Expression) -> Iterator[str | None]:
    if not isinstance(expr.wtype, wtypes.WTuple):
        if isinstance(expr, awst_nodes.VarExpression):
            yield expr.name
        else:
            yield None
    elif isinstance(expr, awst_nodes.TupleExpression):
        for item in expr.items:
            yield from _expand_tuple_vars(item)
    elif isinstance(expr, awst_nodes.VarExpression):
        yield from _build_tuple_item_names(expr.name, expr.wtype, expr.source_location)
    else:
        yield from ([None] * sum_wtypes_arity(expr.wtype.types))


def _build_tuple_item_names(
    base_name: str, wtype: wtypes.WType, source_location: SourceLocation
) -> list[str]:
    if not isinstance(wtype, wtypes.WTuple):
        return [base_name]
    return [
        name
        for idx, item_type in enumerate(wtype.types)
        for name in _build_tuple_item_names(
            format_tuple_index(wtype, base_name, idx), item_type, source_location
        )
    ]
