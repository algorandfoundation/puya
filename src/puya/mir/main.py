import functools
import operator

import attrs

from puya.algo_constants import MAX_SCRATCH_SLOT_NUMBER
from puya.context import ArtifactCompileContext
from puya.errors import CodeError
from puya.ir import models as ir
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor import IRTraverser
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder, build_new_slot_sub
from puya.mir.context import ProgramMIRContext
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend, bits_to_bytes


def program_ir_to_mir(context: ArtifactCompileContext, program_ir: ir.Program) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)

    result = models.Program(
        kind=program_ir.kind,
        main=_lower_subroutine_to_mir(ctx, program_ir.main, is_main=True),
        subroutines=[
            _lower_subroutine_to_mir(ctx, ir_sub, is_main=False)
            for ir_sub in program_ir.subroutines
        ],
        avm_version=program_ir.avm_version,
    )
    if HasNewSlotVisitor.visit(program_ir):
        allocation_ops, allocation_slot = _build_slot_allocation_ops(ctx)
        result.main.body[0].mem_ops[0:0] = allocation_ops
        result.subroutines.append(build_new_slot_sub(allocation_slot))
    global_stack_allocation(ctx, result)
    return result


@attrs.define
class HasNewSlotVisitor(IRTraverser):
    has_new_slot: bool = False

    @classmethod
    def visit(cls, program: ir.Program) -> bool:
        visitor = cls()
        for sub in program.all_subroutines:
            visitor.visit_all_blocks(sub.body)
        return visitor.has_new_slot

    def visit_new_slot(self, _: ir.NewSlot) -> None:
        self.has_new_slot = True


def _build_slot_allocation_ops(context: ProgramMIRContext) -> tuple[list[models.Op], int]:
    available_slots = set(range(MAX_SCRATCH_SLOT_NUMBER + 1))
    program = context.program
    available_slots = available_slots - program.reserved_scratch_space
    # need at least two slots for allocations to be possible at all
    # 1 for the allocation_slot, and 1 for some actual data
    if len(available_slots) <= 1:
        raise CodeError(
            "not enough available slots for dynamic slot usage, consider reserving less slots",
            program.source_location,
        )
    allocation_slot = min(available_slots)
    available_slots.remove(allocation_slot)
    # TODO: check this
    init = functools.reduce(operator.or_, (1 << (a - 1) for a in available_slots), 0)
    allocation_value = init.to_bytes(bits_to_bytes(init.bit_length()))
    return [
        models.Byte(
            # TODO: would need to pad this if we allowed "freeing" slots
            value=allocation_value,
            encoding=AVMBytesEncoding.base16,
            source_location=None,
        ),
        models.IntrinsicOp(
            op_code="store",
            immediates=[allocation_slot],
            consumes=1,
            produces=(),
            source_location=None,
        ),
    ], allocation_slot


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
        source_location=subroutine.source_location,
    )
