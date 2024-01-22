from collections.abc import Sequence

import attrs
import structlog

from puya.avm_type import AVMType
from puya.errors import InternalError
from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext

logger = structlog.get_logger(__name__)


def get_lazy_fstack(subroutine: mir.MemorySubroutine) -> list[mir.StoreVirtual]:
    result = list[mir.StoreVirtual]()
    seen_local_ids = set[str]()
    # TODO: consider more than the entry block
    entry = subroutine.body[0]
    # if entry is re-entrant then can't lazy allocate anything
    if entry.predecessors:
        return result
    for op in entry.ops:
        if isinstance(op, mir.StoreVirtual) and op.local_id not in seen_local_ids:
            seen_local_ids.add(op.local_id)
            result.append(op)
    return result


def get_local_id_types(subroutine: mir.MemorySubroutine) -> dict[str, AVMType]:
    variable_mapping = dict[str, AVMType]()
    for block in subroutine.all_blocks:
        for op in block.ops:
            if isinstance(op, mir.StoreVirtual):
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
        match variable_type_mapping[variable]:
            # treat any as uint when pre-allocating
            case AVMType.uint64 | AVMType.any:
                uint64_vars.append(variable)
            case AVMType.bytes:
                byte_vars.append(variable)
            case _ as unknown:
                raise InternalError(f"Unhandled AVM type in f-stack allocation: {unknown}")
    return mir.Allocate(bytes_vars=byte_vars, uint64_vars=uint64_vars)


def allocate_locals_on_stack(ctx: SubroutineCodeGenContext) -> None:
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
        for index, op in enumerate(block.ops):
            match op:
                case mir.StoreVirtual(
                    local_id=local_id, source_location=src_location, atype=atype
                ):
                    block.ops[index] = mir.StoreFStack(
                        local_id=local_id,
                        source_location=src_location,
                        insert=op in first_store_ops,
                        atype=atype,
                    )
                    removed_virtual = True
                case mir.LoadVirtual(
                    local_id=local_id,
                    source_location=src_location,
                    atype=atype,
                ):
                    block.ops[index] = mir.LoadFStack(
                        local_id=local_id,
                        source_location=src_location,
                        atype=atype,
                    )
                    removed_virtual = True
                case mir.RetSub() as retsub:
                    block.ops[index] = attrs.evolve(retsub, f_stack_size=len(all_variables))
    if removed_virtual:
        ctx.invalidate_vla()
