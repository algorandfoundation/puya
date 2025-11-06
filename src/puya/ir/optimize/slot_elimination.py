import itertools
from collections import defaultdict

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import SlotAllocationStrategy
from puya.ir.to_text_visitor import render_program
from puya.ir.visitor import IRTraverser
from puya.program_refs import ContractReference, LogicSigReference

logger = log.get_logger(__name__)


def slot_elimination(
    ctx: ArtifactCompileContext,
    program: models.Program,
    *,
    ref: ContractReference | LogicSigReference,
) -> None:
    logger.debug(f"removing local static slots in {program.kind} program of {ref}")
    # needs to be considered across the entire program
    dynamic_slot_allocation_required = False
    for sub in program.all_subroutines:
        visitor = _SlotGatherer()
        visitor.visit_all_blocks(sub.body)
        logger.debug(
            f"auto reserving slots in {sub.id}, {sorted(visitor.intrinsic_slots)}",
            location=sub.source_location,
        )
        program.slot_allocation.reserved |= visitor.intrinsic_slots

        local_slots = itertools.count()
        modified = False
        for slot_reg, (block, ass, new_slot) in visitor.new_slot_registers.items():
            if slot_reg in visitor.non_slot_register_reads:
                dynamic_slot_allocation_required = True
            else:
                block.ops.remove(ass)
                modified = True
                reads = visitor.slot_reads[slot_reg]
                if reads:
                    logger.debug(
                        f"eliminating local static slot assigned to {slot_reg.local_id}",
                        location=slot_reg.source_location,
                    )
                    slot_const = models.SlotConstant(
                        value=next(local_slots),
                        ir_type=new_slot.ir_type,
                        source_location=new_slot.source_location,
                    )
                    for read in reads:
                        read.slot = slot_const
                    for _, write in visitor.slot_writes[slot_reg]:
                        write.slot = slot_const
                else:
                    logger.debug(
                        f"eliminating unused local slot assigned to {slot_reg.local_id}",
                        location=slot_reg.source_location,
                    )
                    for write_block, write in visitor.slot_writes[slot_reg]:
                        write_block.ops.remove(write)
        if modified:
            sub.validate_with_ssa()
    if dynamic_slot_allocation_required:
        logger.debug("Using dynamic slot allocation strategy")
        program.slot_allocation.strategy = SlotAllocationStrategy.dynamic
    else:
        logger.debug("Slot allocation not required")
        program.slot_allocation.strategy = SlotAllocationStrategy.none

    if ctx.options.output_ssa_ir:
        render_program(ctx, program, qualifier="ssa.slot")


class _SlotGatherer(IRTraverser):
    active_block: models.BasicBlock

    def __init__(self) -> None:
        self.intrinsic_slots = set[int]()
        # Registers containing any assigned new_slot:
        self.new_slot_registers = dict[
            models.Register, tuple[models.BasicBlock, models.Assignment, models.NewSlot]
        ]()
        # Any registers that have read usages outside of a WriteSlot or ReadSlot
        self.non_slot_register_reads = set[models.Register]()
        self.slot_reads = defaultdict[models.Value, list[models.ReadSlot]](list)
        self.slot_writes = defaultdict[
            models.Value, list[tuple[models.BasicBlock, models.WriteSlot]]
        ](list)

    def visit_block(self, block: models.BasicBlock) -> None:
        self.active_block = block
        super().visit_block(block)

    def visit_assignment(self, ass: models.Assignment) -> None:
        # capture new slots
        if isinstance(ass.source, models.NewSlot):
            (slot_register,) = ass.targets
            self.new_slot_registers[slot_register] = self.active_block, ass, ass.source
        else:
            ass.source.accept(self)

    def visit_read_slot(self, read: models.ReadSlot) -> None:
        # don't visit read.slot
        self.slot_reads[read.slot].append(read)

    def visit_write_slot(self, write: models.WriteSlot) -> None:
        write.value.accept(self)
        # don't visit write.slot
        self.slot_writes[write.slot].append((self.active_block, write))

    def visit_phi(self, phi: models.Phi) -> None:
        for arg in phi.args:
            self.visit_phi_argument(arg)

    def visit_register(self, reg: models.Register) -> None:
        self.non_slot_register_reads.add(reg)

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        super().visit_intrinsic_op(intrinsic)
        if intrinsic.op in (AVMOp.load, AVMOp.store):
            (slot,) = intrinsic.immediates
            assert isinstance(slot, int)
            self.intrinsic_slots.add(slot)
