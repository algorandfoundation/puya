from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.optimize import post_ssa_optimizer
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_artifact_to_cssa, remove_phi_nodes

logger = log.get_logger(__name__)


def destructure_ssa(
    context: CompileContext, artifact_ir: models.ModuleArtifact
) -> models.ModuleArtifact:
    artifact_ir = convert_artifact_to_cssa(context, artifact_ir)
    artifact_ir = remove_phi_nodes(context, artifact_ir)
    artifact_ir = coalesce_locals(context, artifact_ir)
    artifact_ir = sequentialize_parallel_copies(context, artifact_ir)
    if context.options.optimization_level > 0:
        artifact_ir = post_ssa_optimizer(context, artifact_ir)
    return artifact_ir
