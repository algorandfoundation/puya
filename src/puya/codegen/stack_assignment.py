import structlog

from puya.codegen import ops
from puya.codegen.context import ProgramCodeGenContext
from puya.codegen.stack_baileys import baileys
from puya.codegen.stack_frame_allocation import allocate_locals_on_stack
from puya.codegen.stack_koopmans import koopmans
from puya.codegen.stack_simplify_teal import simplify_teal_ops

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
