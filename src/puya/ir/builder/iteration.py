import typing
from collections.abc import Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import (
    Expression,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder._utils import assert_value, assign, assign_intrinsic_op, mkblocks, reassign
from puya.ir.builder.assignment import handle_assignment
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BasicBlock,
    ConditionalBranch,
    Goto,
    GotoNth,
    Intrinsic,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
)
from puya.ir.types_ import IRType
from puya.ir.utils import lvalue_items
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def handle_for_in_loop(context: IRFunctionBuildContext, statement: awst_nodes.ForInLoop) -> None:
    sequence = statement.sequence
    has_enumerate = False
    reverse_items = False
    reverse_index = False

    while True:
        match sequence:
            case awst_nodes.Enumeration():
                if has_enumerate:
                    raise CodeError(
                        "Nested enumeration is not currently supported",
                        sequence.source_location,
                    )
                sequence = sequence.expr
                has_enumerate = True
            case awst_nodes.Reversed():
                sequence = sequence.expr
                reverse_items = not reverse_items
                if not has_enumerate:
                    reverse_index = not reverse_index
            case _:
                break

    if not has_enumerate:
        index_var = None
        item_var = statement.items
    else:
        if not (
            isinstance(statement.items, awst_nodes.TupleExpression)
            and len(statement.items.items) == 2
        ):
            # TODO: fix this
            raise CodeError(
                "when using uenumerate(), loop variables must be an unpacked two item tuple",
                statement.sequence.source_location,
            )
        index_var, item_var = lvalue_items(statement.items)

    match sequence:
        case awst_nodes.Range(
            start=range_start, stop=range_stop, step=range_step, source_location=range_loc
        ):
            _iterate_urange(
                context,
                loop_body=statement.loop_body,
                item_var=item_var,
                index_var=index_var,
                statement_loc=statement.source_location,
                range_start=range_start,
                range_stop=range_stop,
                range_step=range_step,
                range_loc=range_loc,
                reverse_items=reverse_items,
                reverse_index=reverse_index,
            )
        case awst_nodes.Expression(wtype=wtypes.WTuple()) as tuple_expression:
            tuple_items = context.visitor.visit_and_materialise(tuple_expression)
            if not tuple_items:
                logger.debug("Skipping ForInStatement which iterates an empty sequence.")
            else:
                _iterate_tuple(
                    context,
                    loop_body=statement.loop_body,
                    item_var=item_var,
                    index_var=index_var,
                    tuple_items=tuple_items,
                    statement_loc=statement.source_location,
                    reverse_index=reverse_index,
                    reverse_items=reverse_items,
                )
        case awst_nodes.Expression(wtype=wtypes.bytes_wtype) as bytes_expression:
            bytes_value = context.visitor.visit_and_materialise_single(bytes_expression)
            (byte_length,) = assign(
                context,
                temp_description="bytes_length",
                source=Intrinsic(
                    op=AVMOp.len_,
                    args=[bytes_value],
                    source_location=statement.source_location,
                ),
                source_location=statement.source_location,
            )

            def get_byte_at_index(index_register: Register) -> ValueProvider:
                return Intrinsic(
                    op=AVMOp.extract3,
                    args=[
                        bytes_value,
                        index_register,
                        UInt64Constant(value=1, source_location=None),
                    ],
                    source_location=item_var.source_location,
                )

            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=byte_length,
                get_value_at_index=get_byte_at_index,
                item_var=item_var,
                index_var=index_var,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case awst_nodes.Expression(
            wtype=wtypes.ARC4Array(element_type=wtypes.WType(immutable=False))
        ):
            raise InternalError(
                "Attempted iteration of an ARC4 array of mutable objects",
                sequence.source_location,
            )
        case awst_nodes.Expression(
            wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() as array_wtype
        ) as arc4_array_expression:
            iterator = arc4.build_for_in_array(
                context,
                array_wtype,
                arc4_array_expression,
                statement.source_location,
            )
            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=iterator.size,
                get_value_at_index=iterator.get_value_at_index,
                item_var=item_var,
                index_var=index_var,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case _:
            raise InternalError("Unsupported for in loop sequence", statement.source_location)


def _check_urange_will_loop(
    context: IRFunctionBuildContext,
    *,
    stop: Value,
    start: Value,
    after_for: BasicBlock,
    statement_loc: SourceLocation,
) -> None:
    (preamble,) = mkblocks(statement_loc, "for_preamble")
    (should_loop,) = assign_intrinsic_op(
        context,
        target="should_loop",
        op=AVMOp.lt,
        args=[start, stop],
        source_location=statement_loc,
    )
    context.block_builder.terminate(
        ConditionalBranch(
            condition=should_loop,
            non_zero=preamble,
            zero=after_for,
            source_location=statement_loc,
        )
    )
    context.block_builder.activate_block(preamble)
    context.ssa.seal_block(preamble)


def _iterate_urange(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    item_var: awst_nodes.Lvalue,
    index_var: awst_nodes.Lvalue | None,
    statement_loc: SourceLocation,
    range_start: Expression,
    range_stop: Expression,
    range_step: Expression,
    range_loc: SourceLocation,
    reverse_items: bool,
    reverse_index: bool,
) -> None:
    header, body, footer, increment_block, next_block = mkblocks(
        statement_loc,
        "for_header",
        "for_body",
        "for_footer",
        "for_increment",
        "after_for",
    )

    step = context.visitor.visit_and_materialise_single(range_step)
    stop = context.visitor.visit_and_materialise_single(range_stop)
    start = context.visitor.visit_and_materialise_single(range_start)
    assert_value(context, step, source_location=statement_loc, comment="Step cannot be zero")

    iteration_count_minus_one: Register | None
    if reverse_items or reverse_index:
        # The following code will result in negative uints if we don't pre-check the urange
        # params
        _check_urange_will_loop(
            context,
            stop=stop,
            start=start,
            after_for=next_block,
            statement_loc=statement_loc,
        )

        # Determine the iteration count by doing the equivalent of
        # ceiling((stop - start) / step)
        # which is
        # floor((stop - start) / step) + (mod((stop - start), step) != 0)
        (range_length,) = assign_intrinsic_op(
            context,
            target="range_length",
            source_location=statement_loc,
            op=AVMOp.sub,
            args=[
                stop,
                start,
            ],
        )

        (range_mod_step,) = assign_intrinsic_op(
            context,
            target="range_mod_step",
            source_location=statement_loc,
            op=AVMOp.mod,
            args=[range_length, step],
        )
        (range_mod_step_not_zero,) = assign_intrinsic_op(
            context,
            target="range_mod_step_not_zero",
            source_location=statement_loc,
            op=AVMOp.neq,
            args=[range_mod_step, 0],
        )

        (range_floor_div_step,) = assign_intrinsic_op(
            context,
            target="range_floor_div_step",
            source_location=statement_loc,
            op=AVMOp.div_floor,
            args=[
                range_length,
                step,
            ],
        )
        (iteration_count,) = assign_intrinsic_op(
            context,
            target="iteration_count",
            source_location=statement_loc,
            op=AVMOp.add,
            args=[
                range_floor_div_step,
                range_mod_step_not_zero,
            ],
        )
        (iteration_count_minus_one,) = assign_intrinsic_op(
            context,
            target="iteration_count_minus_one",
            source_location=statement_loc,
            op=AVMOp.sub,
            args=[
                iteration_count,
                1,
            ],
        )
    else:
        iteration_count_minus_one = None

    if reverse_items and iteration_count_minus_one:
        (range_delta,) = assign_intrinsic_op(
            context,
            target="range_delta",
            source_location=statement_loc,
            op=AVMOp.mul,
            args=[step, iteration_count_minus_one],
        )
        (stop,) = assign(
            context,
            temp_description="stop",
            source_location=statement_loc,
            source=start,
        )
        (start,) = assign_intrinsic_op(
            context,
            target="start",
            source_location=statement_loc,
            op=AVMOp.add,
            args=[start, range_delta],
        )

    (range_item,) = assign(
        context,
        source=start,
        temp_description="range_item",
        source_location=item_var.source_location,
    )

    index_var_src_loc = index_var.source_location if index_var else None
    range_index: Register | None = None
    if index_var:
        (range_index,) = assign(
            context,
            source=UInt64Constant(value=0, source_location=None),
            temp_description="range_index",
            source_location=index_var_src_loc,
        )

    context.block_builder.goto_and_activate(header)
    if reverse_items:
        (continue_looping,) = assign(
            context,
            source=(
                Intrinsic(
                    op=AVMOp(">="),
                    args=[_refresh_mutated_variable(context, range_item), stop],
                    source_location=range_loc,
                )
            ),
            temp_description="continue_looping",
            source_location=range_loc,
        )
    else:
        (continue_looping,) = assign(
            context,
            source=(
                Intrinsic(
                    op=AVMOp("<"),
                    args=[_refresh_mutated_variable(context, range_item), stop],
                    source_location=range_loc,
                )
            ),
            temp_description="continue_looping",
            source_location=range_loc,
        )

    context.block_builder.terminate(
        ConditionalBranch(
            condition=continue_looping,
            non_zero=body,
            zero=next_block,
            source_location=statement_loc,
        )
    )

    context.block_builder.activate_block(body)

    handle_assignment(
        context,
        target=item_var,
        value=_refresh_mutated_variable(context, range_item),
        assignment_location=item_var.source_location,
    )
    if index_var and range_index:
        if reverse_index and iteration_count_minus_one:
            (next_index,) = assign_intrinsic_op(
                context,
                target="next_index",
                source_location=index_var.source_location,
                op=AVMOp.sub,
                args=[iteration_count_minus_one, _refresh_mutated_variable(context, range_index)],
            )
            handle_assignment(
                context,
                target=index_var,
                value=next_index,
                assignment_location=index_var.source_location,
            )
        else:
            handle_assignment(
                context,
                target=index_var,
                value=_refresh_mutated_variable(context, range_index),
                assignment_location=index_var.source_location,
            )

    with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
        loop_body.accept(context.visitor)
    context.block_builder.goto_and_activate(footer)
    context.ssa.seal_block(footer)

    if reverse_items:
        (continue_looping,) = assign(
            context,
            source=(
                Intrinsic(
                    op=AVMOp(">"),
                    args=[_refresh_mutated_variable(context, range_item), stop],
                    source_location=range_loc,
                )
            ),
            temp_description="continue_looping",
            source_location=range_loc,
        )
        context.block_builder.terminate(
            ConditionalBranch(
                condition=continue_looping,
                non_zero=increment_block,
                zero=next_block,
                source_location=statement_loc,
            )
        )
        context.block_builder.activate_block(increment_block)
    else:
        context.block_builder.goto_and_activate(increment_block)
    context.ssa.seal_block(increment_block)

    new_range_item_value = Intrinsic(
        op=AVMOp.sub if reverse_items else AVMOp.add,
        args=[_refresh_mutated_variable(context, range_item), step],
        source_location=range_loc,
    )
    reassign(context, range_item, new_range_item_value, statement_loc)
    if range_index and index_var:
        assign_intrinsic_op(
            context,
            target=range_index,
            op=AVMOp("+"),
            args=[
                _refresh_mutated_variable(context, range_index),
                UInt64Constant(value=1, source_location=None),
            ],
            source_location=index_var.source_location,
        )
    if reverse_items:
        context.block_builder.goto(body)
    else:
        context.block_builder.goto(header)
    context.ssa.seal_block(header)
    context.ssa.seal_block(body)
    context.ssa.seal_block(next_block)

    context.block_builder.activate_block(next_block)


def _iterate_indexable(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    item_var: awst_nodes.Lvalue,
    index_var: awst_nodes.Lvalue | None,
    statement_loc: SourceLocation,
    indexable_size: Value,
    get_value_at_index: typing.Callable[[Register], ValueProvider],
    reverse_items: bool,
    reverse_index: bool,
) -> None:
    header, body, footer, next_block = mkblocks(
        statement_loc,
        "for_header",
        "for_body",
        "for_footer",
        "after_for",
    )

    (index_internal,) = assign(
        context,
        source=UInt64Constant(value=0, source_location=None),
        temp_description="item_index_internal",
        source_location=None,
    )
    (reverse_index_internal,) = assign(
        context,
        source=indexable_size,
        temp_description="reverse_index_internal",
        source_location=None,
    )

    context.block_builder.goto_and_activate(header)
    (continue_looping,) = assign(
        context,
        source=(
            Intrinsic(
                op=AVMOp.lt,
                args=[_refresh_mutated_variable(context, index_internal), indexable_size],
                source_location=statement_loc,
            )
        ),
        temp_description="continue_looping",
        source_location=statement_loc,
    )

    context.block_builder.terminate(
        ConditionalBranch(
            condition=continue_looping,
            non_zero=body,
            zero=next_block,
            source_location=statement_loc,
        )
    )
    context.ssa.seal_block(body)

    context.block_builder.activate_block(body)

    current_index_internal = _refresh_mutated_variable(context, index_internal)
    if reverse_items or reverse_index:
        (reverse_index_internal,) = assign_intrinsic_op(
            context,
            target=reverse_index_internal,
            source_location=None,
            op=AVMOp.sub,
            args=[_refresh_mutated_variable(context, reverse_index_internal), 1],
        )
        handle_assignment(
            context,
            target=item_var,
            value=get_value_at_index(
                reverse_index_internal if reverse_items else current_index_internal
            ),
            assignment_location=item_var.source_location,
        )

        if index_var:
            handle_assignment(
                context,
                target=index_var,
                value=reverse_index_internal if reverse_index else current_index_internal,
                assignment_location=index_var.source_location,
            )
    else:
        handle_assignment(
            context,
            target=item_var,
            value=get_value_at_index(current_index_internal),
            assignment_location=item_var.source_location,
        )
        if index_var:
            handle_assignment(
                context,
                target=index_var,
                value=current_index_internal,
                assignment_location=index_var.source_location,
            )

    with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
        loop_body.accept(context.visitor)
    context.block_builder.goto_and_activate(footer)
    context.ssa.seal_block(footer)
    context.ssa.seal_block(next_block)
    new_index_internal_value = Intrinsic(
        op=AVMOp("+"),
        args=[
            _refresh_mutated_variable(context, index_internal),
            UInt64Constant(value=1, source_location=None),
        ],
        source_location=None,
    )
    reassign(context, index_internal, new_index_internal_value, source_location=None)

    context.block_builder.goto(header)
    context.ssa.seal_block(header)

    context.block_builder.activate_block(next_block)


def _iterate_tuple(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    item_var: awst_nodes.Lvalue,
    index_var: awst_nodes.Lvalue | None,
    tuple_items: Sequence[Value],
    statement_loc: SourceLocation,
    reverse_index: bool,
    reverse_items: bool,
) -> None:
    headers = [
        BasicBlock(comment=f"for_header_{index}", source_location=statement_loc)
        for index, _ in enumerate(tuple_items)
    ]
    if reverse_items:
        headers.reverse()
        tuple_items = [*tuple_items]
        tuple_items.reverse()

    body, footer, next_block = mkblocks(
        statement_loc,
        "for_body",
        "for_footer",
        "after_for",
    )

    tuple_index = context.next_tmp_name("tuple_index")

    for index, (item, header) in enumerate(zip(tuple_items, headers, strict=True)):
        if index == 0:
            context.block_builder.goto_and_activate(header)
            context.ssa.seal_block(header)
            assign(
                context,
                source=UInt64Constant(value=0, source_location=None),
                names=[(tuple_index, None)],
                source_location=None,
            )
        else:
            context.block_builder.activate_block(header, ignore_predecessor_check=True)
        handle_assignment(
            context,
            target=item_var,
            value=item,
            assignment_location=item_var.source_location,
        )
        context.block_builder.goto(body)

    context.ssa.seal_block(body)
    context.block_builder.activate_block(body)
    if index_var:
        if reverse_index:
            (reversed_index,) = assign_intrinsic_op(
                context,
                target="reversed_index",
                source_location=None,
                op=AVMOp.sub,
                args=[
                    len(tuple_items) - 1,
                    context.ssa.read_variable(tuple_index, IRType.uint64, body),
                ],
            )
            handle_assignment(
                context,
                target=index_var,
                value=reversed_index,
                assignment_location=index_var.source_location,
            )
        else:
            handle_assignment(
                context,
                target=index_var,
                value=context.ssa.read_variable(tuple_index, IRType.uint64, body),
                assignment_location=index_var.source_location,
            )

    with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
        loop_body.accept(context.visitor)

    context.block_builder.goto_and_activate(footer)
    context.ssa.seal_block(footer)
    curr_index_internal = context.ssa.read_variable(tuple_index, IRType.uint64, footer)
    (_updated_r,) = assign(
        context,
        source=Intrinsic(
            op=AVMOp("+"),
            args=[curr_index_internal, UInt64Constant(value=1, source_location=None)],
            source_location=None,
        ),
        names=[(tuple_index, None)],
        source_location=None,
    )
    goto_default = Goto(target=next_block, source_location=statement_loc)
    context.block_builder.terminate(
        GotoNth(
            source_location=statement_loc,
            value=curr_index_internal,
            blocks=headers[1:],
            default=goto_default,
        )
    )
    for header in headers[1:]:
        context.ssa.seal_block(header)

    context.ssa.seal_block(next_block)
    context.block_builder.activate_block(next_block)


def _refresh_mutated_variable(context: IRFunctionBuildContext, reg: Register) -> Register:
    """
    Given a register pointing to an underlying root operand (ie name) that is mutated,
    do an SSA read in the current block.

    This is *only* required when there is control flow involved in the generated IR,
    if it's only the builder that needs to loop then it should usually have an updated
    reference to the most recent assigned register which will still be valid because it's
    within the same block.
    """
    return context.ssa.read_variable(reg.name, reg.ir_type, context.block_builder.active_block)
