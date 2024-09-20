import json
import shutil

import algokit_utils
import algokit_utils.config
import pytest
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
)
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig
from puya.arc32 import create_arc32_json
from puya.models import CompiledContract
from puyapy.options import PuyaPyOptions

from tests import EXAMPLES_DIR, VCS_ROOT
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet


def test_debug(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    contract_src = EXAMPLES_DIR / "debug" / "contract.py"
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(contract_src,),
            optimization_level=1,
            debug_level=2,
            output_source_map=False,
            output_arc32=False,
            output_teal=False,
        )
    )
    (contract,) = result.teal
    assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"
    approval_src = algokit_utils.replace_template_variables(
        contract.approval_program.teal_src, {"A_MULT": 1000}
    )
    clear_src = contract.clear_program.teal_src
    arc32 = create_arc32_json(approval_src, clear_src, contract.metadata)
    app_spec = algokit_utils.ApplicationSpecification.from_json(arc32)
    client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
    )
    client.create()

    atc = AtomicTransactionComposer()
    client.compose_call(atc, "test", x=1, y=2, z=3)
    simulate_request = SimulateRequest(
        txn_groups=[],
        allow_more_logs=True,
        allow_empty_signatures=True,
        exec_trace_config=SimulateTraceConfig(
            enable=True,
            stack_change=True,
            scratch_change=True,
            state_change=True,
        ),
    )
    response = atc.simulate(algod_client, simulate_request)
    # puya dir

    dest = VCS_ROOT / ".." / "avm-debugger" / "sampleWorkspace" / "puya"

    # contract
    shutil.copy(contract_src, dest / "contract.py")
    # source map
    source_map = "DebugContract.approval.puya.map"
    (dest / source_map).write_bytes(contract.approval_program.debug_info or b"")
    # trace
    (dest / "contract.simulate.json").write_text(json.dumps(response.simulate_response))

    program_hash = response.simulate_response["txn-groups"][0]["txn-results"][0]["exec-trace"][
        "approval-program-hash"
    ]
    sources = {
        "txn-group-sources": [
            {
                "sourcemap-location": f"./{source_map}",
                "hash": program_hash,
            }
        ]
    }
    (dest / "sources.json").write_text(json.dumps(sources))
