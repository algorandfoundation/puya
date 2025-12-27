import typing

import algokit_algod_client.models as algod
import algokit_utils as au
import attrs
import pytest
from algokit_common import ProgramSourceMap

from puya.arc56 import create_arc56_json
from puya.compilation_artifacts import CompiledContract, DebugInfo
from puyapy.options import PuyaPyOptions
from tests import TEST_CASES_DIR
from tests.utils.compile import compile_src_from_options

pytestmark = pytest.mark.localnet


def test_debug(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> None:
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
    approval_src = localnet.app.replace_template_variables(
        contract.approval_program.teal_src, {"A_MULT": 1000}
    )
    app_spec = create_arc56_json(
        metadata=contract.metadata,
        approval_program=attrs.evolve(contract.approval_program, teal_src=approval_src),  # type: ignore[misc]
        clear_program=contract.clear_program,
        template_prefix="TMPL_",
    )
    factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=localnet,
            app_spec=app_spec,
            default_sender=account.addr,
        )
    )
    client, create_result = factory.send.bare.create()

    txns = client.create_transaction.call(
        au.AppClientMethodCallParams(
            method="test",
            args=[1, 2, 3],
        )
    )
    composer = localnet.new_group().add_transaction(txns.transactions[0], account.signer)
    response = composer.simulate(
        exec_trace_config=algod.SimulateTraceConfig(
            enable=True,
        )
    )
    approval_debug_map = contract.approval_program.debug_info
    assert approval_debug_map is not None
    assert isinstance(create_result.compiled_approval, au.CompiledTeal)
    _check_teal_map_with_puya_map(create_result.compiled_approval.source_map, approval_debug_map)
    assert response.simulate_response is not None
    _check_trace_with_puya_map(response.simulate_response, approval_debug_map)

    clear_debug_map = contract.clear_program.debug_info
    assert clear_debug_map is not None
    assert isinstance(create_result.compiled_clear, au.CompiledTeal)
    _check_teal_map_with_puya_map(create_result.compiled_clear.source_map, clear_debug_map)


Json = dict[str, typing.Any]


def _check_teal_map_with_puya_map(
    teal_source_map: ProgramSourceMap | None, puya_map: DebugInfo
) -> None:
    assert teal_source_map is not None, "missing source map"
    op_pc_offset = puya_map.op_pc_offset
    # if a non-zero offset is provided increment by 1 to account for version byte in line_to_pc map
    if op_pc_offset:
        op_pc_offset += 1
    line, pcs = sorted(teal_source_map.line_to_pc.items())[op_pc_offset]
    pc_offset = pcs[0]

    puya_source_map = ProgramSourceMap(attrs.asdict(puya_map))
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


def _check_trace_with_puya_map(simulate: algod.SimulateResponse, puya_map: DebugInfo) -> None:
    op_pc_offset = puya_map.op_pc_offset
    exec_trace = simulate.txn_groups[0].txn_results[0].exec_trace
    assert exec_trace is not None
    approval_trace = exec_trace.approval_program_trace
    assert approval_trace is not None
    offset_trace = approval_trace[op_pc_offset]
    pc_offset = offset_trace.pc
    missing_pcs = [
        pc
        for pc in (pc_trace.pc for pc_trace in approval_trace)
        if pc >= pc_offset and (pc - pc_offset) not in puya_map.pc_events
    ]
    assert not missing_pcs, "expected relative pcs to be in pc_events"
