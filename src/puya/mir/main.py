import functools
import operator
import typing

from puya.algo_constants import MAX_SCRATCH_SLOT_NUMBER
from puya.context import ArtifactCompileContext
from puya.ir import models as ir
from puya.ir.models import SlotAllocationStrategy
from puya.log import get_logger
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder, build_new_slot_sub
from puya.mir.context import ProgramMIRContext
from puya.mir.output import output_memory_ir
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend, bits_to_bytes

logger = get_logger(__name__)


def program_ir_to_mir(context: ArtifactCompileContext, program_ir: ir.Program) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)

    mir_main = _lower_subroutine_to_mir(ctx, program_ir.main, is_main=True)
    mir_subroutines = [
        _lower_subroutine_to_mir(ctx, ir_sub, is_main=False) for ir_sub in program_ir.subroutines
    ]
    match program_ir.slot_allocation.strategy:
        case SlotAllocationStrategy.none:
            mir_allocation = None
        case SlotAllocationStrategy.dynamic:
            mir_allocation = _build_slot_allocation(program_ir)
            mir_subroutines.append(build_new_slot_sub(mir_allocation.allocation_slot))
        case unexpected:
            typing.assert_never(unexpected)
    result = models.Program(
        kind=program_ir.kind,
        main=mir_main,
        subroutines=mir_subroutines,
        avm_version=program_ir.avm_version,
        slot_allocation=mir_allocation,
    )
    if ctx.options.output_memory_ir:
        output_memory_ir(ctx, result, qualifier="build")
    global_stack_allocation(ctx, result)
    return result


def _build_slot_allocation(program: ir.Program) -> models.SlotAllocation:
    available_slots = set(range(MAX_SCRATCH_SLOT_NUMBER + 1))
    available_slots = available_slots - program.slot_allocation.reserved
    # need at least two slots for allocations to be possible at all
    # 1 for the allocation_slot, and 1 for some actual data
    if len(available_slots) <= 1:
        logger.error(
            "not enough available slots for dynamic slot usage, consider reserving less slots",
            location=program.source_location,
        )
        allocation_slot = 0
    else:
        allocation_slot = min(available_slots)
        available_slots.remove(allocation_slot)
    # remaining available slots are indicated with their bit set to 1
    init = functools.reduce(operator.or_, (1 << (a - 1) for a in available_slots), 0)
    # note: would need to pad this if we allowed "freeing" slots
    allocation_value = init.to_bytes(bits_to_bytes(MAX_SCRATCH_SLOT_NUMBER + 1))
    return models.SlotAllocation(
        allocation_slot=allocation_slot,
        allocation_map=allocation_value,
    )


def _lower_subroutine_to_mir(
    context: ProgramMIRContext, subroutine: ir.Subroutine, *, is_main: bool
) -> models.MemorySubroutine:
    builder = MemoryIRBuilder(context=context, current_subroutine=subroutine, is_main=is_main)
    body = [builder.lower_block_to_mir(block) for block in subroutine.body]
    signature = models.Signature(
        name=subroutine.id,
        parameters=[
            models.Parameter(name=p.name, local_id=p.local_id, atype=p.atype)
            for p in subroutine.parameters
        ],
        returns=[r.avm_type for r in subroutine.returns],
    )
    return models.MemorySubroutine(
        id=context.subroutine_names[subroutine],
        signature=signature,
        is_main=is_main,
        body=body,
        pre_alloc=None,  # filled in by f_stack_allocation
        source_location=subroutine.source_location,
    )
