from collections.abc import Sequence

import attrs

from puya import log
from puya.avm_type import AVMType
from puya.errors import CodeError, InternalError
from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext
from puya.mir.stack import Stack
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


def get_lazy_fstack(subroutine: mir.MemorySubroutine) -> list[mir.AbstractStore]:
    result = list[mir.AbstractStore]()
    seen_local_ids = set[str]()
    # TODO: consider more than the entry block
    entry = subroutine.body[0]
    # if entry is re-entrant then can't lazy allocate anything
    if entry.predecessors:
        return result
    for op in entry.ops:
        if isinstance(op, mir.AbstractStore) and op.local_id not in seen_local_ids:
            seen_local_ids.add(op.local_id)
            result.append(op)
    return result


def get_local_id_types(subroutine: mir.MemorySubroutine) -> dict[str, AVMType]:
    variable_mapping = dict[str, AVMType]()
    for block in subroutine.all_blocks:
        for op in block.ops:
            if isinstance(op, mir.AbstractStore):
                try:
                    existing_type = variable_mapping[op.local_id]
                except KeyError:
                    existing_type = op.atype
                variable_mapping[op.local_id] = existing_type | op.atype
    return variable_mapping


def get_allocate_op(
    subroutine: mir.MemorySubroutine, all_variables: Sequence[str]
) -> mir.Allocate:
    # determine variables to allocate at beginning of frame,
    # and order them so bytes are listed first, followed by uints
    byte_vars = []
    uint64_vars = []
    variable_type_mapping = get_local_id_types(subroutine)
    for variable in all_variables:
        match variable_type_mapping.get(variable):
            case AVMType.uint64:
                uint64_vars.append(variable)
            case AVMType.bytes:
                byte_vars.append(variable)
            case AVMType.any:
                raise InternalError(
                    "Encountered AVM type any on preamble construction",
                    subroutine.preamble.source_location,
                )
            case None:
                raise CodeError(
                    f"Undefined register: {variable}."
                    " This can be caused by attempting to reference variables that are only"
                    " defined in other execution paths.",
                    subroutine.preamble.source_location,
                )
            case _ as unknown:
                raise InternalError(f"Unhandled AVM type in f-stack allocation: {unknown}")
    return mir.Allocate(bytes_vars=byte_vars, uint64_vars=uint64_vars)


def f_stack_allocation(ctx: SubroutineCodeGenContext) -> None:
    all_variables = ctx.vla.all_variables
    if not all_variables:
        return

    subroutine = ctx.subroutine
    first_store_ops = get_lazy_fstack(subroutine)
    allocate_on_first_store = [op.local_id for op in first_store_ops]

    unsorted_allocate_at_entry = [x for x in all_variables if x not in allocate_on_first_store]
    if unsorted_allocate_at_entry:
        allocate = get_allocate_op(subroutine, unsorted_allocate_at_entry)
        allocate_at_entry = allocate.allocate_on_entry
        subroutine.preamble.ops.append(allocate)
    else:
        allocate_at_entry = []
    subroutine.preamble.f_stack_out = allocate_at_entry
    logger.debug(f"{subroutine.signature.name} f-stack entry: {allocate_at_entry}")
    logger.debug(f"{subroutine.signature.name} f-stack on first store: {allocate_on_first_store}")

    subroutine.body[0].f_stack_in = allocate_at_entry
    all_f_stack = [*allocate_at_entry, *allocate_on_first_store]
    subroutine.body[0].f_stack_out = all_f_stack
    for block in subroutine.body[1:]:
        block.f_stack_in = block.f_stack_out = all_f_stack

    removed_virtual = False
    for block in subroutine.body:
        stack = Stack.begin_block(subroutine, block)
        for index, op in enumerate(block.ops):
            match op:
                case mir.AbstractStore() as store:
                    insert = op in first_store_ops
                    if insert:
                        depth = stack.xl_height - 1
                    else:
                        depth = stack.fxl_height - stack.f_stack.index(store.local_id) - 1

                    block.ops[index] = attrs_extend(
                        mir.StoreFStack,
                        store,
                        depth=depth,
                        frame_index=stack.fxl_height - depth - 1,
                        insert=insert,
                    )
                    removed_virtual = True
                case mir.AbstractLoad() as load:
                    depth = stack.fxl_height - stack.f_stack.index(load.local_id) - 1
                    block.ops[index] = attrs_extend(
                        mir.LoadFStack,
                        load,
                        depth=depth,
                        frame_index=stack.fxl_height - depth - 1,
                    )
                    removed_virtual = True
                case mir.RetSub() as retsub:
                    block.ops[index] = attrs.evolve(
                        retsub, fx_height=len(stack.f_stack) + len(stack.x_stack)
                    )
            op.accept(stack)
    if removed_virtual:
        ctx.invalidate_vla()
