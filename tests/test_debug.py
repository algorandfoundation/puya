import typing

import algokit_utils
import algokit_utils.config
import attrs
import pytest
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
)
from algosdk.source_map import SourceMap
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig
from puya.arc32 import create_arc32_json
from puya.models import CompiledContract, DebugInfo
from puyapy.options import PuyaPyOptions

from tests import TEST_CASES_DIR
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet


def test_debug(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    contract_src = TEST_CASES_DIR / "debug" / "contract.py"
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(contract_src,),
            optimization_level=1,
            debug_level=2,
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
    approval_debug_map = contract.approval_program.debug_info
    assert approval_debug_map is not None
    clear_debug_map = contract.clear_program.debug_info
    assert clear_debug_map is not None
    assert client.approval
    _check_teal_map_with_puya_map(client.approval.source_map, approval_debug_map)
    _check_trace_with_puya_map(response.simulate_response, approval_debug_map)

    assert client.clear
    _check_teal_map_with_puya_map(client.clear.source_map, clear_debug_map)


Json = dict[str, typing.Any]


def _check_teal_map_with_puya_map(teal_source_map: SourceMap, puya_map: DebugInfo) -> None:
    op_pc_offset = puya_map.op_pc_offset
    # if a non-zero offset is provided increment by 1 to account for version byte in line_to_pc map
    if op_pc_offset:
        op_pc_offset += 1
    line, pcs = sorted(teal_source_map.line_to_pc.items())[op_pc_offset]
    pc_offset = pcs[0]

    puya_source_map = SourceMap(attrs.asdict(puya_map))
    events = puya_map.pc_events
    max_puya_pc = max(puya_source_map.pc_to_line) + pc_offset
    assert max_puya_pc in teal_source_map.pc_to_line, "expected max puya pc to be in teal src map"
    assert (
        max_puya_pc + 1 not in teal_source_map.pc_to_line
    ), "expected teal pc to not go beyond puya pc"
    missing_event_pcs = [
        pc
        for pc in (int(pc_str) + pc_offset for pc_str in events)
        if pc not in teal_source_map.pc_to_line
    ]
    assert not missing_event_pcs, "expected all event pcs to be in teal source map"


def _check_trace_with_puya_map(simulate: Json, puya_map: DebugInfo) -> None:
    op_pc_offset = puya_map.op_pc_offset
    approval_trace = simulate["txn-groups"][0]["txn-results"][0]["exec-trace"][
        "approval-program-trace"
    ]
    offset_trace = approval_trace[op_pc_offset]
    pc_offset = offset_trace["pc"]
    pc_events = {int(pc): event for pc, event in puya_map.pc_events.items()}
    missing_pcs = [
        pc
        for pc in (int(pc_trace["pc"]) for pc_trace in approval_trace)
        if pc >= pc_offset and (pc - pc_offset) not in pc_events
    ]
    assert not missing_pcs, "expected relative pcs to be in pc_events"
