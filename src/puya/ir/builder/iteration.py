import typing

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.arc4_types import effective_array_encoding
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4, arrays
from puya.ir.builder._tuple_util import build_tuple_registers, get_tuple_item_values
from puya.ir.builder._utils import (
    assert_value,
    assign_intrinsic_op,
    assign_targets,
    assign_temp,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    ConditionalBranch,
    GotoNth,
    Intrinsic,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
)
from puya.ir.types_ import PrimitiveIRType
from puya.ir.utils import lvalue_items
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class LoopVariables(typing.NamedTuple):
    item_registers: typing.Sequence[Register]
    index_: Register | None

    def refresh_assignment(self, context: IRFunctionBuildContext) -> "LoopVariables":
        item = [_refresh_mutated_variable(context, i) for i in self.item_registers]
        if self.index_ is None:
            index = None
        else:
            index = _refresh_mutated_variable(context, self.index_)
        return LoopVariables(item, index)


class LoopAssigner:
    def __init__(
        self, context: IRFunctionBuildContext, items: awst_nodes.Lvalue, *, has_enumerate: bool
    ):
        self._context: typing.Final = context
        self._items: typing.Final = items
        self.has_enumerate: typing.Final = has_enumerate

    def assign_user_loop_vars(
        self, item_provider: ValueProvider, index_provider: ValueProvider
    ) -> LoopVariables:
        registers = self._build_registers_from_lvalue(self._items)
        if not self.has_enumerate:
            index_register = None
            item_registers = registers
        else:
            (index_register, *item_registers) = registers
        assign_targets(
            self._context,
            source=item_provider,
            targets=item_registers,
            assignment_location=self._items.source_location,
        )
        if index_register:
            assign_targets(
                self._context,
                source=index_provider,
                targets=[index_register],
                assignment_location=self._items.source_location,
            )
        return LoopVariables(item_registers, index_register)

    def _build_registers_from_lvalue(self, target: awst_nodes.Lvalue) -> list[Register]:
        match target:
            case awst_nodes.VarExpression(name=var_name, source_location=var_loc, wtype=var_type):
                return build_tuple_registers(self._context, var_name, var_type, var_loc)
            case awst_nodes.TupleExpression() as tup_expr:
                tuple_items = lvalue_items(tup_expr)
                return [
                    reg for item in tuple_items for reg in self._build_registers_from_lvalue(item)
                ]
            case _:
                raise CodeError(
                    "unsupported assignment target in loop", self._items.source_location
                )


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
                        "Nested enumeration is not currently supported", sequence.source_location
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

    assign_user_loop_vars = LoopAssigner(
        context,
        items=statement.items,
        has_enumerate=has_enumerate,
    )

    match sequence.wtype:
        case wtypes.uint64_range_wtype if isinstance(sequence, awst_nodes.Range):
            _iterate_urange(
                context,
                loop_body=statement.loop_body,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                urange=sequence,
                reverse_items=reverse_items,
                reverse_index=reverse_index,
            )
        case wtypes.WTuple(types=item_types):
            if not item_types:
                logger.debug("Skipping ForInStatement which iterates an empty sequence.")
            else:
                _iterate_tuple(
                    context,
                    loop_body=statement.loop_body,
                    assigner=assign_user_loop_vars,
                    tuple_expr=sequence,
                    statement_loc=statement.source_location,
                    reverse_index=reverse_index,
                    reverse_items=reverse_items,
                )
        case wtypes.BytesWType():
            bytes_value = context.visitor.visit_and_materialise_single(sequence)
            byte_length = assign_temp(
                context,
                temp_description="bytes_length",
                source=Intrinsic(
                    op=AVMOp.len_,
                    args=[bytes_value],
                    source_location=statement.source_location,
                ),
                source_location=statement.source_location,
            )

            def get_byte_at_index(index_register: Value) -> ValueProvider:
                return Intrinsic(
                    op=AVMOp.extract3,
                    args=[
                        bytes_value,
                        index_register,
                        UInt64Constant(value=1, source_location=None),
                    ],
                    source_location=statement.items.source_location,
                )

            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=byte_length,
                get_value_at_index=get_byte_at_index,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case wtypes.ARC4Array() as arc4_array_wtype:
            iterator = arc4.build_for_in_array(
                context,
                arc4_array_wtype,
                sequence,
                statement.source_location,
            )
            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=iterator.array_length,
                get_value_at_index=iterator.get_value_at_index,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case wtypes.StackArray(element_type=element_type) as array_wtype:
            arc4_encoding_wtype = effective_array_encoding(array_wtype, sequence.source_location)
            arc4_element_type = arc4_encoding_wtype.element_type
            iterator = arc4.build_for_in_array(
                context,
                arc4_encoding_wtype,
                sequence,
                statement.source_location,
            )

            def read_and_decode(index: Value) -> ValueProvider:
                item_vp = iterator.get_value_at_index(index)
                return arc4.maybe_decode_arc4_value_provider(
                    context,
                    item_vp,
                    arc4_element_type,
                    element_type,
                    statement.source_location,
                    temp_description="value_at_index",
                )

            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=iterator.array_length,
                get_value_at_index=read_and_decode,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case wtypes.ReferenceArray():
            iterator = arrays.build_for_in_array(
                context,
                sequence,
                statement.source_location,
            )
            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=iterator.array_length,
                get_value_at_index=iterator.get_value_at_index,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                reverse_index=reverse_index,
                reverse_items=reverse_items,
            )
        case _:
            raise InternalError("Unsupported ForInLoop sequence", statement.source_location)


def _iterate_urange(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    assigner: LoopAssigner,
    statement_loc: SourceLocation,
    urange: awst_nodes.Range,
    reverse_items: bool,
    reverse_index: bool,
) -> None:
    step = context.visitor.visit_and_materialise_single(urange.step)
    stop = context.visitor.visit_and_materialise_single(urange.stop)
    start = context.visitor.visit_and_materialise_single(urange.start)
    assert_value(context, step, error_message="Step cannot be zero", source_location=statement_loc)

    if reverse_items or reverse_index:
        return _iterate_urange_with_reversal(
            context,
            loop_body=loop_body,
            assigner=assigner,
            statement_loc=statement_loc,
            start=start,
            stop=stop,
            step=step,
            range_loc=urange.source_location,
            reverse_items=reverse_items,
            reverse_index=reverse_index,
        )
    else:
        return _iterate_urange_simple(
            context,
            loop_body=loop_body,
            assigner=assigner,
            statement_loc=statement_loc,
            start=start,
            stop=stop,
            step=step,
            range_loc=urange.source_location,
        )


def _iterate_urange_simple(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    assigner: LoopAssigner,
    statement_loc: SourceLocation,
    start: Value,
    stop: Value,
    step: Value,
    range_loc: SourceLocation,
) -> None:
    body = context.block_builder.mkblock(loop_body, "for_body")
    header, footer, next_block = context.block_builder.mkblocks(
        "for_header", "for_footer", "after_for", source_location=statement_loc
    )

    loop_vars = assigner.assign_user_loop_vars(
        start, UInt64Constant(value=0, source_location=None)
    )
    context.block_builder.goto(header)
    with context.block_builder.activate_open_block(header):
        (current_range_item,), current_range_index = loop_vars.refresh_assignment(context)
        continue_looping = assign_intrinsic_op(
            context,
            target="continue_looping",
            op=AVMOp.lt,
            args=[current_range_item, stop],
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
        with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(context.visitor)

        context.block_builder.goto(footer)
        if context.block_builder.try_activate_block(footer):
            assign_intrinsic_op(
                context,
                target=current_range_item,
                op=AVMOp.add,
                args=[current_range_item, step],
                source_location=range_loc,
            )
            if current_range_index:
                assign_intrinsic_op(
                    context,
                    target=current_range_index,
                    op=AVMOp.add,
                    args=[current_range_index, 1],
                    source_location=range_loc,
                )
            context.block_builder.goto(header)

    context.block_builder.activate_block(next_block)


def _iterate_urange_with_reversal(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    assigner: LoopAssigner,
    statement_loc: SourceLocation,
    start: Value,
    stop: Value,
    step: Value,
    range_loc: SourceLocation,
    reverse_items: bool,
    reverse_index: bool,
) -> None:
    assert reverse_items or reverse_index
    body = context.block_builder.mkblock(loop_body, "for_body")
    header, footer, increment_block, next_block = context.block_builder.mkblocks(
        "for_header", "for_footer", "for_increment", "after_for", source_location=statement_loc
    )

    # The following code will result in underflow if we don't pre-check the urange
    # params
    should_loop = assign_intrinsic_op(
        context,
        target="should_loop",
        op=AVMOp.lt,
        args=[start, stop],
        source_location=statement_loc,
    )
    context.block_builder.terminate(
        ConditionalBranch(
            condition=should_loop,
            non_zero=header,
            zero=next_block,
            source_location=statement_loc,
        )
    )

    context.block_builder.activate_block(header)
    # iteration_count = ((stop - 1) - start) // step + 1
    # => iteration_count - 1 = (stop - start - 1) // step
    range_length = assign_intrinsic_op(
        context,
        target="range_length",
        op=AVMOp.sub,
        args=[stop, start],
        source_location=range_loc,
    )
    range_length_minus_one = assign_intrinsic_op(
        context,
        target="range_length_minus_one",
        op=AVMOp.sub,
        args=[range_length, 1],
        source_location=range_loc,
    )
    iteration_count_minus_one = assign_intrinsic_op(
        context,
        target="iteration_count_minus_one",
        op=AVMOp.div_floor,
        args=[range_length_minus_one, step],
        source_location=range_loc,
    )
    range_delta = assign_intrinsic_op(
        context,
        target="range_delta",
        op=AVMOp.mul,
        args=[step, iteration_count_minus_one],
        source_location=range_loc,
    )
    max_range_item = assign_intrinsic_op(
        context,
        target="max_range_item",
        op=AVMOp.add,
        args=[start, range_delta],
        source_location=range_loc,
    )
    loop_vars = assigner.assign_user_loop_vars(
        start if not reverse_items else max_range_item,
        (
            UInt64Constant(value=0, source_location=None)
            if not reverse_index
            else iteration_count_minus_one
        ),
    )
    context.block_builder.goto(body)

    with context.block_builder.activate_open_block(body):
        (current_range_item,), current_range_index = loop_vars.refresh_assignment(context)

        with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(context.visitor)

        context.block_builder.goto(footer)
        if context.block_builder.try_activate_block(footer):
            continue_looping_op = Intrinsic(
                op=AVMOp.lt,
                args=(
                    [current_range_item, max_range_item]
                    if not reverse_items
                    else [start, current_range_item]
                ),
                source_location=range_loc,
            )
            continue_looping = assign_temp(
                context,
                source=continue_looping_op,
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
            assign_intrinsic_op(
                context,
                target=current_range_item,
                op=AVMOp.add if not reverse_items else AVMOp.sub,
                args=[current_range_item, step],
                source_location=range_loc,
            )
            if current_range_index:
                assign_intrinsic_op(
                    context,
                    target=current_range_index,
                    op=AVMOp.add if not reverse_index else AVMOp.sub,
                    args=[current_range_index, 1],
                    source_location=range_loc,
                )
            context.block_builder.goto(body)

    context.block_builder.activate_block(next_block)


def _iterate_indexable(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    assigner: LoopAssigner,
    statement_loc: SourceLocation,
    indexable_size: Value,
    get_value_at_index: typing.Callable[[Value], ValueProvider],
    reverse_items: bool,
    reverse_index: bool,
) -> None:
    body = context.block_builder.mkblock(loop_body, "for_body")
    header, footer, next_block = context.block_builder.mkblocks(
        "for_header", "for_footer", "after_for", source_location=statement_loc
    )

    index_internal = assign_temp(
        context,
        source=UInt64Constant(value=0, source_location=None),
        temp_description="item_index_internal",
        source_location=None,
    )
    reverse_index_internal = assign_temp(
        context,
        source=indexable_size,
        temp_description="reverse_index_internal",
        source_location=None,
    )
    context.block_builder.goto(header)

    with context.block_builder.activate_open_block(header):
        current_index_internal = _refresh_mutated_variable(context, index_internal)
        if not (reverse_items or reverse_index):
            continue_looping = assign_intrinsic_op(
                context,
                target="continue_looping",
                op=AVMOp.lt,
                args=[current_index_internal, indexable_size],
                source_location=statement_loc,
            )
        else:
            continue_looping = assign_intrinsic_op(
                context,
                target="continue_looping",
                op=AVMOp.gt,
                args=[_refresh_mutated_variable(context, reverse_index_internal), 0],
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

        context.block_builder.activate_block(body)
        if reverse_items or reverse_index:
            reverse_index_internal = assign_intrinsic_op(
                context,
                target=reverse_index_internal,
                op=AVMOp.sub,
                args=[_refresh_mutated_variable(context, reverse_index_internal), 1],
                source_location=None,
            )
        assigner.assign_user_loop_vars(
            get_value_at_index(
                reverse_index_internal if reverse_items else current_index_internal
            ),
            reverse_index_internal if reverse_index else current_index_internal,
        )
        with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(context.visitor)
        context.block_builder.goto(footer)

        if context.block_builder.try_activate_block(footer):
            if not (reverse_items and reverse_index):
                assign_intrinsic_op(
                    context,
                    target=index_internal,
                    op=AVMOp.add,
                    args=[current_index_internal, 1],
                    source_location=None,
                )
            context.block_builder.goto(header)

    context.block_builder.activate_block(next_block)


def _iterate_tuple(
    context: IRFunctionBuildContext,
    *,
    loop_body: awst_nodes.Block,
    assigner: LoopAssigner,
    tuple_expr: awst_nodes.Expression,
    statement_loc: SourceLocation,
    reverse_index: bool,
    reverse_items: bool,
) -> None:
    tuple_values = context.visitor.visit_and_materialise(tuple_expr)
    assert isinstance(tuple_expr.wtype, wtypes.WTuple), "tuple_expr wtype must be WTuple"
    tuple_wtype = tuple_expr.wtype
    max_index = len(tuple_wtype.types) - 1
    loop_counter_name = context.next_tmp_name("loop_counter")

    def assign_counter_and_user_vars(loop_count: int) -> Register:
        counter_reg = context.ssa.new_register(loop_counter_name, PrimitiveIRType.uint64, None)
        assign_targets(
            context,
            source=UInt64Constant(value=loop_count, source_location=None),
            targets=[counter_reg],
            assignment_location=None,
        )
        item_index = loop_count if not reverse_items else (max_index - loop_count)
        item_reg, index_reg = assigner.assign_user_loop_vars(
            get_tuple_item_values(
                tuple_values=tuple_values,
                tuple_wtype=tuple_wtype,
                index=item_index,
                target_wtype=tuple_wtype.types[item_index],
                source_location=statement_loc,
            ),
            UInt64Constant(
                value=loop_count if not reverse_index else (max_index - loop_count),
                source_location=None,
            ),
        )
        if index_reg and not reverse_index:
            return index_reg
        else:
            return counter_reg

    # construct basic blocks
    body = context.block_builder.mkblock(loop_body, "for_body")
    footer, next_block = context.block_builder.mkblocks(
        "for_footer", "after_for", source_location=statement_loc
    )
    headers = {
        idx: context.block_builder.mkblock(statement_loc, f"for_header_{idx}")
        for idx in range(1, len(tuple_wtype.types))
    }

    # first item - assigned in current block
    loop_counter = assign_counter_and_user_vars(0)

    # body
    context.block_builder.goto(body)
    with context.block_builder.activate_open_block(body):
        current_loop_counter = _refresh_mutated_variable(context, loop_counter)
        with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(context.visitor)

        # footer + follow-up headers, iff the loop body doesn't exit unconditionally on first item
        context.block_builder.goto(footer)
        if context.block_builder.try_activate_block(footer):
            # footer
            context.block_builder.terminate(
                GotoNth(
                    value=current_loop_counter,
                    blocks=list(headers.values()),
                    default=next_block,
                    source_location=statement_loc,
                )
            )

            # headers for remaining items
            for idx, header in headers.items():
                context.block_builder.activate_block(header)
                assign_counter_and_user_vars(idx)
                context.block_builder.goto(body)

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
