import typing
from collections.abc import Callable, Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import sequence
from puya.ir.builder._utils import assign, assign_temp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.encodings import wtype_to_encoding
from puya.ir.models import (
    ConditionalBranch,
    GotoNth,
    Intrinsic,
    Register,
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
)
from puya.ir.op_utils import (
    OpFactory,
    assert_value,
    assign_intrinsic_op,
    assign_targets,
    convert_constants,
)
from puya.ir.types_ import PrimitiveIRType, TupleIRType, ir_type_to_ir_types, wtype_to_ir_type
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
            case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
                ir_type = wtype_to_ir_type(target, allow_tuple=True)
                if isinstance(ir_type, TupleIRType):
                    exploded_names = ir_type.build_item_names(var_name)
                else:
                    exploded_names = [var_name]
                ir_types = ir_type_to_ir_types(ir_type)
                return [
                    self._context.new_register(name, ir_type, var_loc)
                    for name, ir_type in zip(exploded_names, ir_types, strict=True)
                ]
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
    loc = statement.source_location
    sequence_ = statement.sequence
    has_enumerate = False
    reverse_items = False
    reverse_index = False

    while True:
        match sequence_:
            case awst_nodes.Enumeration():
                if has_enumerate:
                    raise CodeError(
                        "Nested enumeration is not currently supported", sequence_.source_location
                    )
                sequence_ = sequence_.expr
                has_enumerate = True
            case awst_nodes.Reversed():
                sequence_ = sequence_.expr
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

    match sequence_.wtype:
        case wtypes.uint64_range_wtype if isinstance(sequence_, awst_nodes.Range):
            _iterate_urange(
                context,
                loop_body=statement.loop_body,
                assigner=assign_user_loop_vars,
                statement_loc=statement.source_location,
                urange=sequence_,
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
                    tuple_expr=sequence_,
                    statement_loc=statement.source_location,
                    reverse_index=reverse_index,
                    reverse_items=reverse_items,
                )
        case wtypes.BytesWType():
            bytes_value = context.visitor.visit_and_materialise_single(sequence_)
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
        case (wtypes.ARC4Array() | wtypes.ReferenceArray()) as iterable_wtype:
            array = context.visitor.visit_and_materialise_single(sequence_)

            array_encoding = wtype_to_encoding(iterable_wtype, loc)
            (indexable_size,) = context.visitor.materialise_value_provider(
                sequence.get_length(
                    array_encoding,
                    array,
                    loc,
                ),
                "array_length",
            )

            _iterate_indexable(
                context,
                loop_body=statement.loop_body,
                indexable_size=indexable_size,
                # TODO: consider when array is a register and needs refreshing
                get_value_at_index=lambda index: sequence.read_aggregate_index_and_decode(
                    context, iterable_wtype, [array], [index], loc, check_bounds=False
                ),
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

    # We need two temporary values to act as loop variables to match after-loop
    # iteration variable behavior.
    value_internal = assign_temp(
        context,
        source=start,
        temp_description="value_internal",
        source_location=range_loc,
    )
    if assigner.has_enumerate:
        index_internal = assign_temp(
            context,
            source=UInt64Constant(value=0, source_location=None),
            temp_description="item_index_internal",
            source_location=range_loc,
        )

    context.block_builder.goto(header)
    with context.block_builder.activate_open_block(header):
        value_internal = _refresh_mutated_variable(context, value_internal)
        if assigner.has_enumerate:
            index_internal = _refresh_mutated_variable(context, index_internal)

        factory = OpFactory(context, statement_loc)
        context.block_builder.terminate(
            ConditionalBranch(
                condition=factory.lt(value_internal, stop, "continue_looping"),
                non_zero=body,
                zero=next_block,
                source_location=statement_loc,
            )
        )

        context.block_builder.activate_block(body)

        assigner.assign_user_loop_vars(
            value_internal,
            index_internal
            if assigner.has_enumerate
            else Undefined(source_location=None, ir_type=PrimitiveIRType.uint64),
        )
        with context.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(context.visitor)

        context.block_builder.goto(footer)
        if context.block_builder.try_activate_block(footer):
            _reassign_with_intrinsic_op(
                context,
                target=value_internal,
                op=AVMOp.add,
                args=[value_internal, step],
                source_location=range_loc,
            )
            if assigner.has_enumerate:
                _reassign_with_intrinsic_op(
                    context,
                    target=index_internal,
                    op=AVMOp.add,
                    args=[index_internal, 1],
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
    factory = OpFactory(context, statement_loc)
    context.block_builder.terminate(
        ConditionalBranch(
            condition=factory.lt(start, stop, "should_loop"),
            non_zero=header,
            zero=next_block,
            source_location=statement_loc,
        )
    )

    context.block_builder.activate_block(header)
    # iteration_count = ((stop - 1) - start) // step + 1
    # => iteration_count - 1 = (stop - start - 1) // step
    factory = OpFactory(context, range_loc)
    range_length = factory.sub(stop, start, "range_length")
    range_length_minus_one = factory.sub(range_length, 1, "range_length_minus_one")
    iteration_count_minus_one = factory.div_floor(
        range_length_minus_one, step, "iteration_count_minus_one"
    )
    range_delta = factory.mul(step, iteration_count_minus_one, "range_delta")
    max_range_item = factory.add(start, range_delta, "max_range_item")

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
            if reverse_items:
                continue_looping = factory.lt(start, current_range_item, "continue_looping")
            else:
                continue_looping = factory.lt(
                    current_range_item, max_range_item, "continue_looping"
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
            _reassign_with_intrinsic_op(
                context,
                target=current_range_item,
                op=AVMOp.add if not reverse_items else AVMOp.sub,
                args=[current_range_item, step],
                source_location=range_loc,
            )
            if current_range_index:
                _reassign_with_intrinsic_op(
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
    get_value_at_index: Callable[[Value], ValueProvider],
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
            reverse_index_internal = _reassign_with_intrinsic_op(
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
                _reassign_with_intrinsic_op(
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
    tuple_wtype = tuple_expr.wtype
    assert isinstance(tuple_wtype, wtypes.WTuple), "tuple_expr wtype must be WTuple"

    tuple_values = context.visitor.visit_and_materialise(tuple_expr)

    max_index = len(tuple_wtype.types) - 1
    loop_counter_name = context.next_tmp_name("loop_counter")

    def assign_counter_and_user_vars(loop_count: int) -> Register:
        counter_reg = assign(
            context,
            source=UInt64Constant(value=loop_count, source_location=None),
            name=loop_counter_name,
            assignment_location=None,
        )
        item_index = loop_count if not reverse_items else (max_index - loop_count)
        item_vp = sequence.read_tuple_index(tuple_wtype, tuple_values, item_index, statement_loc)
        item_reg, index_reg = assigner.assign_user_loop_vars(
            item_vp,
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


def _reassign_with_intrinsic_op(
    context: IRFunctionBuildContext,
    *,
    target: Register,
    op: AVMOp,
    args: Sequence[int | Value],
    source_location: SourceLocation | None,
) -> Register:
    intrinsic = Intrinsic(
        op=op,
        args=[convert_constants(a, source_location) for a in args],
        source_location=source_location,
    )
    return assign(
        context,
        source=intrinsic,
        name=target.name,
        ir_type=target.ir_type,
        register_location=target.source_location,
        assignment_location=source_location,
    )
