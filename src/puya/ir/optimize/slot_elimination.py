import itertools

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.visitor import IRTraverser

logger = log.get_logger(__name__)


def slot_elimination(_: CompileContext, subroutine: models.Subroutine) -> bool:
    visitor = RemovableSlotGatherer()
    visitor.visit_all_blocks(subroutine.body)
    local_slots = itertools.count(max(visitor.existing_slots, default=-1) + 1)
    for slot, (ass, new_slot) in visitor.new_slot_registers.items():
        if slot in visitor.excluded_registers:
            continue
        logger.debug(
            f"eliminating local static slot assigned to {slot.local_id}",
            location=slot.source_location,
        )
        replacement = models.SlotConstant(
            value=next(local_slots),
            ir_type=new_slot.ir_type,
            source_location=new_slot.source_location,
        )
        ass.source = replacement
    modified = False
    return modified


@attrs.define
class RemovableSlotGatherer(IRTraverser):
    new_slot_registers: dict[models.Register, tuple[models.Assignment, models.NewSlot]] = (
        attrs.field(factory=dict, init=False)
    )
    """Registers containing any assigned new_slot"""
    excluded_registers: set[models.Register] = attrs.field(factory=set, init=False)
    """Any registers that are not static or local-only"""
    existing_slots: list[int] = attrs.field(factory=list, init=False)

    def visit_assignment(self, ass: models.Assignment) -> None:
        super().visit_assignment(ass)
        if isinstance(ass.source, models.NewSlot):
            (slot_register,) = ass.targets
            self.new_slot_registers[slot_register] = ass, ass.source

    def visit_slot_constant(self, const: models.SlotConstant) -> None:
        self.existing_slots.append(const.value)

    def visit_phi(self, phi: models.Phi) -> None:
        super().visit_phi(phi)
        # registers in phis are not static
        for arg in phi.args:
            self.excluded_registers.add(arg.value)

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        super().visit_invoke_subroutine(callsub)
        # registers passed to other subroutines are not static
        for arg in callsub.args:
            if isinstance(arg, models.Register):
                self.excluded_registers.add(arg)
