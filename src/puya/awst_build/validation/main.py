from puya.awst import (
    nodes as awst_nodes,
)
from puya.awst_build.validation.arc4_copy import validate_arc4_copy_semantics
from puya.awst_build.validation.scratch_slots import validate_scratch_slot_reservations
from puya.context import CompileContext


def validate_awst(context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
    validate_arc4_copy_semantics(context, module_asts)
    validate_scratch_slot_reservations(context, module_asts)
