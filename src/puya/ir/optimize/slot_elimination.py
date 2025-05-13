import itertools

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import SlotAllocationStrategy
from puya.ir.optimize.constant_propagation import constant_replacer
from puya.ir.optimize.dead_code_elimination import remove_unused_variables
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
    # these properties need to be considered across the entire program
    dynamic_slots = 0
    non_local_slots = 0
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
        for slot_reg, (ass, new_slot) in visitor.new_slot_registers.items():
            if slot_reg in visitor.dynamic_registers:
                dynamic_slots += 1
                continue
            if slot_reg in visitor.non_local_registers:
                non_local_slots += 1
                continue
            modified = True
            logger.debug(
                f"eliminating local static slot assigned to {slot_reg.local_id}",
                location=slot_reg.source_location,
            )
            ass.source = models.SlotConstant(
                value=next(local_slots),
                ir_type=new_slot.ir_type,
                source_location=new_slot.source_location,
            )
        if modified:
            # replace any slot constants referenced by other ops
            constant_replacer(ctx, sub)
            # remove now unused assignments
            remove_unused_variables(ctx, sub)
            sub.validate_with_ssa()
    if dynamic_slots or non_local_slots:
        logger.debug("Using dynamic slot allocation strategy")
        program.slot_allocation.strategy = SlotAllocationStrategy.dynamic
    else:
        logger.debug("Slot allocation not required")
        program.slot_allocation.strategy = SlotAllocationStrategy.none

    if ctx.options.output_ssa_ir:
        render_program(ctx, program, qualifier="ssa.slot")


class _SlotGatherer(IRTraverser):
    def __init__(self) -> None:
        self.intrinsic_slots = set[int]()
        # Registers containing any assigned new_slot:
        self.new_slot_registers = dict[models.Register, tuple[models.Assignment, models.NewSlot]]()
        # Any registers that are dynamic:
        self.dynamic_registers = set[models.Register]()
        # Any registers that are not local (passed to other subroutines):
        self.non_local_registers = set[models.Register]()

    def visit_assignment(self, ass: models.Assignment) -> None:
        super().visit_assignment(ass)
        # capture new slots
        if isinstance(ass.source, models.NewSlot):
            (slot_register,) = ass.targets
            self.new_slot_registers[slot_register] = ass, ass.source
        # excluded copied slots
        # if copy propagation has been done it will potentially allow more slots to be removed
        elif isinstance(ass.source, models.Register):
            self.dynamic_registers.add(ass.source)

    def visit_phi_argument(self, arg: models.PhiArgument) -> None:
        # registers involved in phis are considered dynamic
        self.dynamic_registers.add(arg.value)

    def visit_subroutine_return(self, retsub: models.SubroutineReturn) -> None:
        super().visit_subroutine_return(retsub)
        for value in retsub.result:
            # registers that leave a subroutine are non local
            if isinstance(value, models.Register):
                self.non_local_registers.add(value)

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        super().visit_invoke_subroutine(callsub)
        # registers passed to other subroutines are non local
        for arg in callsub.args:
            if isinstance(arg, models.Register):
                self.non_local_registers.add(arg)

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        super().visit_intrinsic_op(intrinsic)
        if intrinsic.op in (AVMOp.load, AVMOp.store):
            slot = intrinsic.immediates[0]
            assert isinstance(slot, int)
            self.intrinsic_slots.add(slot)
