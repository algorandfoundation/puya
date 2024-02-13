import structlog

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.builder.utils import (
    assign,
    mkblocks,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BasicBlock,
    ConditionalBranch,
    Goto,
    Register,
    Switch,
    Value,
)
from puya.ir.types_ import wtype_to_avm_type
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

logger = structlog.get_logger(__name__)


def handle_if_else(context: IRFunctionBuildContext, stmt: awst_nodes.IfElse) -> None:
    # else_body might be unused, if so won't be added, so all good
    if_body, else_body, next_block = mkblocks(
        stmt.source_location,
        stmt.if_branch.description or "if_body",
        (stmt.else_branch and stmt.else_branch.description) or "else_body",
        "after_if_else",
    )

    process_conditional(
        context,
        stmt.condition,
        true=if_body,
        false=else_body if stmt.else_branch else next_block,
        loc=stmt.source_location,
    )
    context.ssa.seal_block(if_body)
    context.ssa.seal_block(else_body)
    _branch(
        context,
        ir_block=if_body,
        ast_block=stmt.if_branch,
        next_ir_block=next_block,
    )
    if stmt.else_branch:
        _branch(
            context,
            ir_block=else_body,
            ast_block=stmt.else_branch,
            next_ir_block=next_block,
        )
    if next_block.predecessors:
        # Activate the "next" block if it is reachable.
        # This might not be the case if all paths within the "if" and "else" branches
        # return early.
        context.block_builder.activate_block(next_block)
    elif next_block.phis or next_block.ops or next_block.terminated:
        # here as a sanity - there shouldn't've been any modifications of "next" block contents
        raise InternalError("next block has no predecessors but does have op(s)")
    context.ssa.seal_block(next_block)


def handle_switch(context: IRFunctionBuildContext, statement: awst_nodes.Switch) -> None:
    case_blocks = dict[Value, BasicBlock]()
    ir_blocks = dict[awst_nodes.Block, BasicBlock]()
    for value, block in statement.cases.items():
        ir_value = context.visitor.visit_and_materialise_single(value)
        case_blocks[ir_value] = lazy_setdefault(
            ir_blocks,
            block,
            lambda b: BasicBlock(
                source_location=b.source_location,
                comment=b.description or f"switch_case_{len(ir_blocks)}",
            ),
        )
    default_block, next_block = mkblocks(
        statement.source_location,
        (statement.default_case and statement.default_case.description) or "switch_case_default",
        "switch_case_next",
    )

    switch_value = context.visitor.visit_and_materialise_single(statement.value)
    goto_default = Goto(
        target=default_block,
        source_location=(
            (statement.default_case and statement.default_case.source_location)
            or statement.source_location
        ),
    )
    context.block_builder.terminate(
        Switch(
            value=switch_value,
            cases=case_blocks,
            default=goto_default,
            source_location=statement.source_location,
        )
    )
    for ir_block in (default_block, *ir_blocks.values()):
        context.ssa.seal_block(ir_block)
    for block, ir_block in ir_blocks.items():
        _branch(context, ir_block, block, next_block)
    if statement.default_case:
        _branch(context, default_block, statement.default_case, next_block)
    else:
        context.block_builder.activate_block(default_block)
        context.block_builder.goto(next_block)
    if next_block.predecessors:
        # Activate the "next" block if it is reachable.
        # This might not be the case if all paths within the "if" and "else" branches
        # return early.
        context.block_builder.activate_block(next_block)
    elif next_block.phis or next_block.ops or next_block.terminated:
        # here as a sanity - there shouldn't've been any modifications of "next" block contents
        raise InternalError("next block has no predecessors but does have op(s)")
    context.ssa.seal_block(next_block)


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
            contd = BasicBlock(source_location=loc, comment=f"{bool_op}_contd")
            if bool_op == "and":
                process_conditional(context, lhs, true=contd, false=false, loc=loc)
            elif bool_op == "or":
                process_conditional(context, lhs, true=true, false=contd, loc=loc)
            else:
                raise InternalError(
                    f"Unhandled boolean operator for short circuiting: {bool_op}", loc
                )
            context.ssa.seal_block(contd)
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
    top, body, next_block = mkblocks(
        statement.source_location,
        "while_top",
        statement.loop_body.description or "while_body",
        "after_while",
    )

    with context.block_builder.enter_loop(on_continue=top, on_break=next_block):
        context.block_builder.goto_and_activate(top)
        process_conditional(
            context,
            statement.condition,
            true=body,
            false=next_block,
            loc=statement.source_location,
        )
        context.ssa.seal_block(body)

        context.block_builder.activate_block(body)
        statement.loop_body.accept(context.visitor)
        context.block_builder.goto(top)
    context.ssa.seal_block(top)
    context.ssa.seal_block(next_block)
    context.block_builder.activate_block(next_block)


def handle_conditional_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.ConditionalExpression
) -> Register:
    # TODO: if expr.true_value and exr.false_value are var expressions,
    #       we can optimize with the `select` op

    true_block, false_block, merge_block = mkblocks(
        expr.source_location, "ternary_true", "ternary_false", "ternary_merge"
    )
    process_conditional(
        context,
        expr.condition,
        true=true_block,
        false=false_block,
        loc=expr.source_location,
    )
    context.ssa.seal_block(true_block)
    context.ssa.seal_block(false_block)

    tmp_var_name = context.next_tmp_name("ternary_result")

    context.block_builder.activate_block(true_block)
    true_vp = context.visitor.visit_expr(expr.true_expr)
    assign(
        context,
        source=true_vp,
        names=[(tmp_var_name, expr.true_expr.source_location)],
        source_location=expr.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(false_block)
    false_vp = context.visitor.visit_expr(expr.false_expr)
    assign(
        context,
        source=false_vp,
        names=[(tmp_var_name, expr.false_expr.source_location)],
        source_location=expr.source_location,
    )
    context.block_builder.goto_and_activate(merge_block)
    context.ssa.seal_block(merge_block)
    result = context.ssa.read_variable(
        variable=tmp_var_name, atype=wtype_to_avm_type(expr), block=merge_block
    )
    return result
