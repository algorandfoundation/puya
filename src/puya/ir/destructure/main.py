import attrs

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.optimize import post_ssa_optimizer
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_to_cssa, destructure_cssa
from puya.ir.to_text_visitor import render_program

logger = log.get_logger(__name__)


def destructure_ssa(context: ArtifactCompileContext, program: models.Program) -> None:
    for subroutine in program.all_subroutines:
        logger.debug(f"Performing SSA IR destructuring for {subroutine.id}")
        convert_to_cssa(subroutine)
        subroutine.validate_with_ssa()
        destructure_cssa(subroutine)
        coalesce_locals(subroutine, context.options.locals_coalescing_strategy)
        sequentialize_parallel_copies(subroutine)
        post_ssa_optimizer(subroutine, context.options.optimization_level)
        attrs.validate(subroutine)
    if context.options.output_destructured_ir:
        render_program(context, program, qualifier="destructured")
