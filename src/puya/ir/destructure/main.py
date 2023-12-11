from pathlib import Path

import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.destructure.coalesce_locals import coalesce_locals
from puya.ir.destructure.parcopy import sequentialize_parallel_copies
from puya.ir.destructure.remove_phi import convert_contract_to_cssa, remove_phi_nodes
from puya.ir.to_text_visitor import output_contract_ir_to_path

logger = structlog.get_logger(__name__)


def destructure_ssa(
    context: CompileContext, contract_ir: models.Contract, contract_ir_base_path: Path
) -> models.Contract:
    contract_ir = convert_contract_to_cssa(context, contract_ir)
    if context.options.output_cssa_ir:
        output_contract_ir_to_path(contract_ir, contract_ir_base_path.with_suffix(".cssa.ir"))
    contract_ir = remove_phi_nodes(context, contract_ir)
    if context.options.output_post_ssa_ir:
        output_contract_ir_to_path(
            contract_ir,
            contract_ir_base_path.with_suffix(".post_ssa.ir"),
        )
    contract_ir = sequentialize_parallel_copies(context, contract_ir)
    if context.options.output_parallel_copies_ir:
        output_contract_ir_to_path(
            contract_ir, contract_ir_base_path.with_suffix(".parallel_copies.ir")
        )
    contract_ir = coalesce_locals(context, contract_ir)
    if context.options.output_final_ir:
        output_contract_ir_to_path(contract_ir, contract_ir_base_path.with_suffix(".final.ir"))
    return contract_ir
