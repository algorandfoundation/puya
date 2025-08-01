import shutil
from pathlib import Path

import algokit_utils
from algosdk.v2client.algod import AlgodClient

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    serialize,
)
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.options import PuyaOptions
from puya.program_refs import ContractReference, LogicSigReference
from puya.utils import unique
from tests import VCS_ROOT
from tests.utils.git import check_for_diff

logger = log.get_logger(__name__)


def compile_contract(
    *,
    awst_path: Path,
    compilation_set: dict[str, Path],
) -> None:
    awst_json = awst_path.read_text("utf8").replace("%DIR%", str(awst_path).replace("\\", "\\\\"))

    out_dirs = unique(compilation_set.values())
    for out_dir in out_dirs:
        shutil.rmtree(out_dir, ignore_errors=True)

    with log.logging_context() as log_ctx, log_exceptions():
        awst = serialize.awst_from_json(awst_json)
        options = PuyaOptions(
            output_arc32=True,
            output_teal=True,
            output_destructured_ir=True,
        )
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

    for out_dir in out_dirs:
        diff = check_for_diff(out_dir, VCS_ROOT)
        assert not diff, f"Uncommitted changes were found:\n{diff}"


def compile_contract_and_clients(
    *,
    awst_path: Path,
    compilation_set: dict[str, Path],
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> dict[str, algokit_utils.ApplicationClient]:
    compile_contract(awst_path=awst_path, compilation_set=compilation_set)
    return {
        contract_id: _make_client(
            algod_client=algod_client, account=account, out_dir=out_dir, contract_id=contract_id
        )
        for contract_id, out_dir in compilation_set.items()
    }


def _make_client(
    *, algod_client: AlgodClient, account: algokit_utils.Account, out_dir: Path, contract_id: str
) -> algokit_utils.ApplicationClient:
    contract_name = contract_id.split("::")[-1]
    app_spec_json = (out_dir / f"{contract_name}.arc32.json").read_text("utf8")

    app_spec = algokit_utils.ApplicationSpecification.from_json(app_spec_json)
    return algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
