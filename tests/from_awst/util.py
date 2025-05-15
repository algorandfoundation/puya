from pathlib import Path

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    serialize,
)
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.options import PuyaOptions
from puya.program_refs import ContractReference, LogicSigReference

logger = log.get_logger(__name__)


def compile_contract(awst_path: Path, compilation_set: dict[str, Path]) -> None:
    awst_json = awst_path.read_text("utf8").replace("%DIR%", str(awst_path).replace("\\", "\\\\"))

    with log.logging_context() as log_ctx, log_exceptions():
        awst = serialize.awst_from_json(awst_json)
        options = PuyaOptions(output_arc32=True)
        compilation_set_validated = dict[ContractReference | LogicSigReference, Path]()
        awst_lookup = {n.id: n for n in awst}
        for target_id, path in compilation_set.items():
            match awst_lookup.get(target_id):
                case awst_nodes.Contract(id=contract_id):
                    compilation_set_validated[contract_id] = path
                case awst_nodes.LogicSignature(id=lsig_id):
                    compilation_set_validated[lsig_id] = path
                case None:
                    logger.error(f"compilation target {target_id!r} not found in AWST")
                case other:
                    logger.error(f"unexpected compilation target type: {type(other).__name__}")
        awst_to_teal(log_ctx, options, compilation_set_validated, {}, awst)
    # note: needs to be outside the with block
    log_ctx.exit_if_errors()
