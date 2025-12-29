import base64
import math
import random
from collections.abc import Callable, Sequence
from pathlib import Path

import algokit_utils
import algokit_utils.config
import algosdk
import pytest
from algokit_utils import (
    ApplicationClient,
    LogicError,
    OnCompleteCallParameters,
    OnCompleteCallParametersDict,
)
from algosdk import abi, constants, transaction
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    SimulateAtomicTransactionResponse,
    TransactionWithSigner,
)
from algosdk.transaction import OnComplete
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig
from nacl.signing import SigningKey

from puya.arc56 import create_arc56_json
from puya.compilation_artifacts import CompiledContract
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.test_execution import decode_logs
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet


def compile_arc32(
    src_path: Path,
    *,
    optimization_level: int = 1,
    debug_level: int = 2,
    contract_name: str | None = None,
    disabled_optimizations: Sequence[str] = (),
    validate_abi_args: bool = True,
) -> str:
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            optimizations_override={o: False for o in disabled_optimizations},
            validate_abi_args=validate_abi_args,
        )
    )
    if contract_name is None:
        (contract,) = result.teal
    else:
        (contract,) = (
            t
            for t in result.teal
            if isinstance(t, CompiledContract)
            if t.metadata.name == contract_name
        )

    assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"
    return create_arc32_json(
        contract.approval_program.teal_src,
        contract.clear_program.teal_src,
        contract.metadata,
    )


def suggested_params(
    *, algod_client: AlgodClient, fee: int | None = None, flat_fee: bool | None = None
) -> algosdk.transaction.SuggestedParams:
    sp = algod_client.suggested_params()

    if fee is not None:
        sp.fee = fee
    if flat_fee is not None:
        sp.flat_fee = flat_fee

    return sp


def _get_app_client(
    example: Path,
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
    *,
    validate_abi_args: bool = True,
) -> ApplicationClient:
    app_spec = _get_app_spec(example, optimization_level, validate_abi_args=validate_abi_args)
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create(transaction_parameters={"note": random.randbytes(8)})

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=400_000,
        ),
    )

    return app_client


def _get_app_spec(
    app_spec_path: Path, optimization_level: int, *, validate_abi_args: bool = True
) -> algokit_utils.ApplicationSpecification:
    return algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            app_spec_path,
            optimization_level=optimization_level,
            disabled_optimizations=() if optimization_level else ("remove_unused_variables",),
            validate_abi_args=validate_abi_args,
        )
    )


def simulate_call(
    app_client: algokit_utils.ApplicationClient,
    method: str,
    extra_budget: int = 20_000,
    txn_params: OnCompleteCallParametersDict | OnCompleteCallParameters | None = None,
    **kwargs: object,
) -> SimulateAtomicTransactionResponse:
    atc = algosdk.atomic_transaction_composer.AtomicTransactionComposer()
    app_client.compose_call(
        atc, call_abi_method=method, transaction_parameters=txn_params, **kwargs
    )
    simulate_response = atc.simulate(
        app_client.algod_client,
        SimulateRequest(
            txn_groups=[],
            extra_opcode_budget=extra_budget,
            allow_unnamed_resources=True,
            exec_trace_config=SimulateTraceConfig(
                enable=True,
                stack_change=True,
                scratch_change=True,
                state_change=True,
            ),
        ),
    )

    if simulate_response.failure_message:
        logic_error_data = algokit_utils.logic_error.parse_logic_error(
            simulate_response.failure_message
        )
        if logic_error_data is None:
            pytest.fail(f"expected LogicError, got {simulate_response.failure_message}")

        if app_client.approval is None:
            pytest.fail("expected approval program")
        raise algokit_utils.LogicError(
            logic_error_str=simulate_response.failure_message,
            program=app_client.approval.teal,
            source_map=app_client.approval.source_map,
            **logic_error_data,
        )
    return simulate_response


def _get_arc4_bytes(arc4_type: str, value: object) -> bytes:
    return algosdk.abi.ABIType.from_string(arc4_type).encode(value)


def _get_global_state(
    sim: SimulateAtomicTransactionResponse,
    key: bytes,
) -> bytes:
    group = sim.simulate_response["txn-groups"][0]
    deltas = group["txn-results"][0]["txn-result"]["global-state-delta"]
    key_b64 = base64.b64encode(key).decode("utf8")
    (match,) = (base64.b64decode(d["value"]["bytes"]) for d in deltas if d["key"] == key_b64)
    return match


def _get_box_state(
    sim: SimulateAtomicTransactionResponse,
    key: bytes,
) -> bytes:
    group = sim.simulate_response["txn-groups"][0]
    trace = group["txn-results"][0]["exec-trace"]["approval-program-trace"]
    scs = [sc for t in trace for sc in t.get("state-changes", [])]
    key_b64 = base64.b64encode(key).decode("utf8")
    *_, sc = (  # get last matching write to state-change
        sc
        for sc in scs
        if sc.get("app-state-type") == "b"  # box
        and sc.get("operation") == "w"  # write
        and sc.get("key") == key_b64  # matching key
    )
    return base64.b64decode(sc["new-value"]["bytes"])


def _map_native_to_algosdk(value: object) -> object:
    # algosdk decoding represents some types differently than their equivalent unencoded types
    # handle those conversions here
    if isinstance(value, str):
        # explicitly return strings unmodified before doing sequence conversions
        return value
    if isinstance(value, bytes):
        # bytes are a sequence of ints
        return list(value)
    if isinstance(value, Sequence):
        # convert tuples to list, as well as recursing into any sequence elements
        return [_map_native_to_algosdk(v) for v in value]
    return value
