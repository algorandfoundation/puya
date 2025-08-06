import attrs

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.critical_edges import split_critical_edges
from puya.ir.destructure.optimize import post_ssa_optimizer
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_to_cssa, destructure_cssa
from puya.ir.to_text_visitor import render_program

logger = log.get_logger(__name__)


def destructure_ssa(context: ArtifactCompileContext, program: models.Program) -> None:
    for subroutine in program.all_subroutines:
        logger.debug(f"Performing SSA IR destructuring for {subroutine.id}")
        if context.options.optimization_level > 0:
            split_critical_edges(subroutine)
            subroutine.validate_with_ssa()
        convert_to_cssa(subroutine)
        logger.stopwatch.lap("IR destructuring convert to cssa")
        subroutine.validate_with_ssa()
        logger.stopwatch.lap("IR destructuring validate ssa")
        destructure_cssa(subroutine)
        logger.stopwatch.lap("IR destructuring cssa")
        coalesce_locals(subroutine, context.options.locals_coalescing_strategy)
        logger.stopwatch.lap("IR destructuring coalesce")
        sequentialize_parallel_copies(subroutine)
        logger.stopwatch.lap("IR destructuring parallel copies")
        post_ssa_optimizer(context, subroutine)
        logger.stopwatch.lap("IR destructuring post optimise")
        attrs.validate(subroutine)
        logger.stopwatch.lap("IR destructuring validate")

    if context.options.output_destructured_ir:
        render_program(context, program, qualifier="destructured")
    logger.stopwatch.lap("IR destructuring")
