import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.mir import models as mir
from puya.mir.context import ProgramMIRContext
from puya.mir.models import FStackPreAllocation
from puya.mir.stack import Stack
from puya.mir.vla import VariableLifetimeAnalysis
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


def _get_lazy_fstack(entry: mir.MemoryBasicBlock) -> dict[str, mir.AbstractStore]:
    # TODO: consider more than the entry block
    # if entry is re-entrant then can't lazy allocate anything
    if entry.predecessors:
        return {}
    result = dict[str, mir.AbstractStore]()
    for op in entry.ops:
        if isinstance(op, mir.AbstractStore):
            result.setdefault(op.local_id, op)
    return result


def _get_local_id_types(subroutine: mir.MemorySubroutine) -> dict[str, AVMType]:
    variable_mapping = dict[str, AVMType]()
    for block in subroutine.body:
        for op in block.ops:
            if isinstance(op, mir.AbstractStore):
                try:
                    existing_type = variable_mapping[op.local_id]
                except KeyError:
                    existing_type = op.atype
                variable_mapping[op.local_id] = existing_type | op.atype
    return variable_mapping


def _get_pre_alloc(
    subroutine: mir.MemorySubroutine, all_variables: Sequence[str]
) -> mir.FStackPreAllocation:
    # determine variables to allocate at beginning of frame,
    # and order them so bytes are listed first, followed by uints
    byte_vars = []
    uint64_vars = []
    variable_type_mapping = _get_local_id_types(subroutine)
    for variable in all_variables:
        match variable_type_mapping.get(variable):
            case AVMType.uint64:
                uint64_vars.append(variable)
            case AVMType.bytes:
                byte_vars.append(variable)
            case AVMType.any:
                raise InternalError(
                    "Encountered AVM type any on preamble construction",
                    subroutine.source_location,
                )
            case None:
                # shouldn't occur, undefined variables should still have an Undefined entry
                # with a type
                raise InternalError(f"Undefined register: {variable}", subroutine.source_location)
            case unexpected:
                typing.assert_never(unexpected)
    return mir.FStackPreAllocation(bytes_vars=byte_vars, uint64_vars=uint64_vars)


def f_stack_allocation(_ctx: ProgramMIRContext, subroutine: mir.MemorySubroutine) -> None:
    vla = VariableLifetimeAnalysis(subroutine)
    all_variables = vla.all_variables
    if not all_variables:
        subroutine.pre_alloc = FStackPreAllocation.empty()
        return

    entry_block = subroutine.body[0]
    first_store_ops = _get_lazy_fstack(entry_block)
    unsorted_pre_allocate = [x for x in all_variables if x not in first_store_ops]
    subroutine.pre_alloc = _get_pre_alloc(subroutine, unsorted_pre_allocate)
    logger.debug(
        f"{subroutine.signature.name} f-stack entry: {subroutine.pre_alloc.allocate_on_entry}"
    )
    logger.debug(f"{subroutine.signature.name} f-stack on first store: {list(first_store_ops)}")

    entry_block.f_stack_in = subroutine.pre_alloc.allocate_on_entry
    entry_block.f_stack_out = [*entry_block.f_stack_in, *first_store_ops]
    # f-stack is initialized in the entry block and doesn't change after that
    for block in subroutine.body[1:]:
        block.f_stack_in = block.f_stack_out = entry_block.f_stack_out

    for block in subroutine.body:
        stack = Stack.begin_block(subroutine, block)
        for index, op in enumerate(block.mem_ops):
            match op:
                case mir.AbstractStore() as store:
                    insert = op in first_store_ops.values()
                    if insert:
                        assert block is entry_block
                        depth = stack.xl_height - 1
                    else:
                        depth = stack.fxl_height - stack.f_stack.index(store.local_id) - 1

                    block.mem_ops[index] = op = attrs_extend(
                        mir.StoreFStack,
                        store,
                        depth=depth,
                        frame_index=stack.fxl_height - depth - 1,
                        insert=insert,
                    )
                case mir.AbstractLoad() as load:
                    depth = stack.fxl_height - stack.f_stack.index(load.local_id) - 1
                    block.mem_ops[index] = op = attrs_extend(
                        mir.LoadFStack,
                        load,
                        depth=depth,
                        frame_index=stack.fxl_height - depth - 1,
                    )
            op.accept(stack)
        match block.terminator:
            case mir.RetSub() as retsub:
                block.terminator = attrs.evolve(
                    retsub, fx_height=len(stack.f_stack) + len(stack.x_stack)
                )
