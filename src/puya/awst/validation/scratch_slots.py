from collections.abc import Collection, Iterator

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ScratchSlotReservationValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)
            for slot, loc in validator.invalid_slot_usages:
                logger.error(
                    f"Scratch slot {slot} has not been reserved.",
                    location=loc,
                )

    def __init__(self) -> None:
        super().__init__()
        self._reserved_slots: Collection[int] = ()
        self._used_slots = list[tuple[int, SourceLocation]]()

    @property
    def invalid_slot_usages(self) -> Iterator[tuple[int, SourceLocation]]:
        for slot, loc in self._used_slots:
            if slot not in self._reserved_slots:
                yield slot, loc

    def visit_contract(self, statement: awst_nodes.Contract) -> None:
        super().visit_contract(statement)
        self._reserved_slots = statement.reserved_scratch_space

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> None:
        super().visit_intrinsic_call(call)
        match call.op_code, call.stack_args:
            case "loads", [awst_nodes.IntegerConstant(value=slot, source_location=loc)]:
                self._used_slots.append((slot, loc))
            case "stores", [awst_nodes.IntegerConstant(value=slot, source_location=loc), *_]:
                self._used_slots.append((slot, loc))
        match call.op_code, call.immediates:
            case "load", [int(slot)]:
                self._used_slots.append((slot, call.source_location))
            case "store", [int(slot)]:
                self._used_slots.append((slot, call.source_location))
