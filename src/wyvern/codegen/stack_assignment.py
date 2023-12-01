import structlog

from wyvern.codegen import ops
from wyvern.codegen.context import ProgramCodeGenContext
from wyvern.codegen.stack_baileys import baileys
from wyvern.codegen.stack_frame_allocation import allocate_locals_on_stack
from wyvern.codegen.stack_koopmans import koopmans
from wyvern.codegen.stack_simplify_teal import simplify_teal_ops

logger = structlog.get_logger(__name__)

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_assignment(
    context: ProgramCodeGenContext, subroutines: list[ops.MemorySubroutine]
) -> None:
    for subroutine in subroutines:
        koopmans(context, subroutine)
        baileys(context, subroutine)
        allocate_locals_on_stack(context, subroutine)
        simplify_teal_ops(context, subroutine)
