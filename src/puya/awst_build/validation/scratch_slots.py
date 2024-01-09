from puya.awst import (
    nodes as awst_nodes,
)
from puya.awst_build.validation.awst_traverser import AwstTraverser
from puya.context import CompileContext


def validate_scratch_slot_reservations(
    context: CompileContext, module_asts: dict[str, awst_nodes.Module]
) -> None:
    for module in module_asts.values():
        for module_statement in module.body:
            ScratchSlotReservationValidator.validate(context, module_statement)


class ScratchSlotReservationValidator(AwstTraverser):
    def __init__(self, context: CompileContext) -> None:
        self._context = context
        self._reserved_slots = set[int]()
        self._used_slots = list[awst_nodes.IntegerConstant]()

    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        super().visit_contract_fragment(statement)
        for reservation in statement.reserved_scratch_space:
            reservation_overlaps_others = False
            for i in range(reservation.start_slot, reservation.stop_slot):
                if i in self._reserved_slots:
                    reservation_overlaps_others = True
                self._reserved_slots.add(i)
            if reservation_overlaps_others:
                self._context.errors.warning(
                    f"Scratch slot reservation {reservation.start_slot}-{reservation.stop_slot}"
                    " overlaps with other reservations",
                    location=reservation.source_location,
                )

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> None:
        super().visit_intrinsic_call(call)
        match call.op_code, call.stack_args:
            case "loads", [awst_nodes.IntegerConstant() as slot]:
                self._used_slots.append(slot)
            case "stores", [awst_nodes.IntegerConstant() as slot, *_]:
                self._used_slots.append(slot)

    def do_validation(self, module_statement: awst_nodes.ModuleStatement) -> None:
        module_statement.accept(self)
        for slot in self._used_slots:
            if slot.value not in self._reserved_slots:
                self._context.errors.error(
                    f"Scratch slot {slot.value} has not been reserved.",
                    location=slot.source_location,
                )

    @classmethod
    def validate(
        cls, context: CompileContext, module_statement: awst_nodes.ModuleStatement
    ) -> None:
        validator = cls(context)
        validator.do_validation(module_statement)
