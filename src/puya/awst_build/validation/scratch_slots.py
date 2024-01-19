from collections.abc import Iterator

from puya.awst import nodes as awst_nodes
from puya.awst_build.validation.awst_traverser import AWSTTraverser
from puya.context import CompileContext
from puya.parse import SourceLocation
from puya.utils import StableSet


class ScratchSlotReservationValidator(AWSTTraverser):
    @classmethod
    def validate(cls, context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
        for module in module_asts.values():
            for module_statement in module.body:
                validator = cls()
                module_statement.accept(validator)
                for slot, loc in validator.invalid_slot_usages:
                    context.errors.error(
                        f"Scratch slot {slot} has not been reserved.",
                        location=loc,
                    )

    def __init__(self) -> None:
        self._reserved_slots = StableSet[int]()
        self._used_slots = list[tuple[int, SourceLocation]]()

    @property
    def invalid_slot_usages(self) -> Iterator[tuple[int, SourceLocation]]:
        for slot, loc in self._used_slots:
            if slot not in self._reserved_slots:
                yield slot, loc

    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        super().visit_contract_fragment(statement)
        # TODO: gather reserved from bases
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
