from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.optimize import post_ssa_optimizer
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_artifact_to_cssa, remove_phi_nodes

logger = log.get_logger(__name__)


def destructure_ssa(context: CompileContext, program: models.Program) -> models.Program:
    program = convert_artifact_to_cssa(context, program)
    program = remove_phi_nodes(context, program)
    program = coalesce_locals(context, program)
    program = sequentialize_parallel_copies(context, program)
    if context.options.optimization_level > 0:
        program = post_ssa_optimizer(context, program)
    return program
