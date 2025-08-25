from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.builder._utils import assign_tuple
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import BasicBlock, ConditionalBranch, Switch, Value, ValueProvider, ValueTuple
from puya.ir.op_utils import OpFactory
from puya.ir.types_ import TupleIRType, ir_type_to_ir_types, wtype_to_ir_type
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

logger = log.get_logger(__name__)


def handle_if_else(context: IRFunctionBuildContext, stmt: awst_nodes.IfElse) -> None:
    if_body = context.block_builder.mkblock(stmt.if_branch, "if_body")
    else_body = None
    if stmt.else_branch:
        else_body = context.block_builder.mkblock(stmt.else_branch, "else_body")
    next_block = context.block_builder.mkblock(stmt.source_location, "after_if_else")

    process_conditional(
        context,
        stmt.condition,
        true=if_body,
        false=else_body or next_block,
        loc=stmt.source_location,
    )
    _branch(context, if_body, stmt.if_branch, next_block)
    if else_body:
        assert stmt.else_branch
        _branch(context, else_body, stmt.else_branch, next_block)
    # activate the "next" block if it is reachable, which  might not be the case
    # if all paths within the "if" and "else" branches return early
    context.block_builder.try_activate_block(next_block)


def handle_switch(context: IRFunctionBuildContext, statement: awst_nodes.Switch) -> None:
    switch_value, *remainder = context.visitor.visit_and_materialise(statement.value)
    if remainder:
        raise CodeError(
            "matching against tuple values is not supported", statement.value.source_location
        )

    case_blocks = dict[Value, BasicBlock]()
    blocks_to_visit = dict[awst_nodes.Block, BasicBlock]()
    for value, block in statement.cases.items():
        ir_value, *remainder = context.visitor.visit_and_materialise(value)
        if remainder:
            raise CodeError(
                "matching against tuple values is not supported", value.source_location
            )
        if ir_value in case_blocks:
            logger.error("code block is unreachable", location=block.source_location)
        else:
            case_blocks[ir_value] = lazy_setdefault(
                blocks_to_visit,
                block,
                lambda _: context.block_builder.mkblock(
                    block,  # noqa: B023
                    f"switch_case_{len(blocks_to_visit)}",
                ),
            )
    next_block = context.block_builder.mkblock(statement.source_location, "switch_case_next")
    if statement.default_case is None:
        default_block = next_block
    else:
        default_block = lazy_setdefault(
            blocks_to_visit,
            statement.default_case,
            lambda b: context.block_builder.mkblock(
                b, "switch_case_default", fallback_location=statement.source_location
            ),
        )

    context.block_builder.terminate(
        Switch(
            value=switch_value,
            cases=case_blocks,
            default=default_block,
            source_location=statement.source_location,
        )
    )
    for awst_block, ir_block in blocks_to_visit.items():
        _branch(context, ir_block, awst_block, next_block)

    # activate the "next" block if it is reachable, which  might not be the case
    # if all code paths within the cases return early
    context.block_builder.try_activate_block(next_block)


def _branch(
    context: IRFunctionBuildContext,
    ir_block: BasicBlock,
    ast_block: awst_nodes.Block,
    next_ir_block: BasicBlock,
) -> None:
    context.block_builder.activate_block(ir_block)
    ast_block.accept(context.visitor)
    context.block_builder.goto(next_ir_block)


def process_conditional(
    context: IRFunctionBuildContext,
    expr: awst_nodes.Expression,
    *,
    true: BasicBlock,
    false: BasicBlock,
    loc: SourceLocation,
) -> None:
    if expr.wtype != wtypes.bool_wtype:
        raise InternalError(
            "_process_conditional should only be used for boolean conditionals", loc
        )
    match expr:
        case awst_nodes.BooleanBinaryOperation(
            op=bool_op, left=lhs, right=rhs, source_location=loc
        ):
            # Short circuit boolean binary operators in a conditional context.
            contd = context.block_builder.mkblock(loc, f"{bool_op}_contd")
            if bool_op == "and":
                process_conditional(context, lhs, true=contd, false=false, loc=loc)
            elif bool_op == "or":
                process_conditional(context, lhs, true=true, false=contd, loc=loc)
            else:
                raise InternalError(
                    f"Unhandled boolean operator for short circuiting: {bool_op}", loc
                )
            context.block_builder.activate_block(contd)
            process_conditional(context, rhs, true=true, false=false, loc=loc)
        case awst_nodes.Not(expr=expr, source_location=loc):
            process_conditional(context, expr, true=false, false=true, loc=loc)
        case _:
            condition_value = context.visitor.visit_and_materialise_single(expr)
            context.block_builder.terminate(
                ConditionalBranch(
                    condition=condition_value,
                    non_zero=true,
                    zero=false,
                    source_location=loc,
                )
            )


def handle_while_loop(context: IRFunctionBuildContext, statement: awst_nodes.WhileLoop) -> None:
    top, next_block = context.block_builder.mkblocks(
        "while_top", "after_while", source_location=statement.source_location
    )
    body = context.block_builder.mkblock(statement.loop_body, "while_body")
    context.block_builder.goto(top)
    with context.block_builder.activate_open_block(top):
        process_conditional(
            context,
            statement.condition,
            true=body,
            false=next_block,
            loc=statement.source_location,
        )
        context.block_builder.activate_block(body)
        with context.block_builder.enter_loop(on_continue=top, on_break=next_block):
            statement.loop_body.accept(context.visitor)
        context.block_builder.goto(top)

    context.block_builder.activate_block(next_block)


def handle_conditional_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.ConditionalExpression
) -> ValueProvider:
    # if lhs and rhs are both guaranteed to not produce side effects, we can use a simple select op
    # TODO: expand detection of side-effect free to include "pure" ops
    expr_ir_type = wtype_to_ir_type(expr, allow_tuple=True)
    if (
        (not isinstance(expr_ir_type, TupleIRType))
        and isinstance(
            expr.true_expr, awst_nodes.VarExpression | awst_nodes.CompileTimeConstantExpression
        )
        and isinstance(
            expr.false_expr, awst_nodes.VarExpression | awst_nodes.CompileTimeConstantExpression
        )
    ):
        false_reg = context.visitor.visit_and_materialise_single(expr.false_expr)
        true_reg = context.visitor.visit_and_materialise_single(expr.true_expr)
        condition_value = context.visitor.visit_and_materialise_single(expr.condition)
        intrinsic_factory = OpFactory(context, expr.source_location)
        return intrinsic_factory.select(
            condition=condition_value,
            true=true_reg,
            false=false_reg,
            temp_desc="select",
            ir_type=expr_ir_type,
        )
    true_block, false_block, merge_block = context.block_builder.mkblocks(
        "ternary_true", "ternary_false", "ternary_merge", source_location=expr.source_location
    )
    tmp_var_name = context.next_tmp_name("ternary_result")
    if isinstance(expr_ir_type, TupleIRType):
        tmp_var_names = expr_ir_type.build_item_names(tmp_var_name)
    else:
        tmp_var_names = [tmp_var_name]
    tmp_var_ir_types = ir_type_to_ir_types(expr_ir_type)

    process_conditional(
        context,
        expr.condition,
        true=true_block,
        false=false_block,
        loc=expr.source_location,
    )

    context.block_builder.activate_block(true_block)
    true_vp = context.visitor.visit_expr(expr.true_expr)
    assign_tuple(
        context,
        source=true_vp,
        names=tmp_var_names,
        ir_types=tmp_var_ir_types,
        assignment_location=expr.true_expr.source_location,
        register_location=expr.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(false_block)
    false_vp = context.visitor.visit_expr(expr.false_expr)
    assign_tuple(
        context,
        source=false_vp,
        names=tmp_var_names,
        ir_types=tmp_var_ir_types,
        assignment_location=expr.false_expr.source_location,
        register_location=expr.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(merge_block)
    result = [
        context.ssa.read_variable(variable=name, ir_type=ir_type, block=merge_block)
        for name, ir_type in zip(tmp_var_names, tmp_var_ir_types, strict=True)
    ]
    if isinstance(expr_ir_type, TupleIRType):
        return ValueTuple(
            values=result, ir_type=expr_ir_type, source_location=expr.source_location
        )
    (result_value,) = result
    return result_value
