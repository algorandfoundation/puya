import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.optimize import post_ssa_optimizer
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_contract_to_cssa, remove_phi_nodes

logger = structlog.get_logger(__name__)


def destructure_ssa(context: CompileContext, contract_ir: models.Contract) -> models.Contract:
    contract_ir = convert_contract_to_cssa(context, contract_ir)
    contract_ir = remove_phi_nodes(context, contract_ir)
    contract_ir = coalesce_locals(context, contract_ir)
    contract_ir = sequentialize_parallel_copies(context, contract_ir)
    if context.options.optimization_level > 0:
        contract_ir = post_ssa_optimizer(context, contract_ir)
    return contract_ir
