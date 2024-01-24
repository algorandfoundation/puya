from puya.awst import nodes as awst_nodes
from puya.awst_build.validation.arc4_copy import ARC4CopyValidator
from puya.awst_build.validation.scratch_slots import ScratchSlotReservationValidator
from puya.context import CompileContext


def validate_awst(context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
    ARC4CopyValidator.validate(context, module_asts)
    ScratchSlotReservationValidator.validate(context, module_asts)
