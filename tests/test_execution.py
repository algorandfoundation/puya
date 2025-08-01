import base64
import collections
import inspect
import os
import random
import re
import typing
from collections.abc import Callable, Collection, Iterable, Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import algokit_utils
import algosdk.constants
import attrs
import prettytable
import pytest
from algokit_utils import (
    Account,
    LogicError,
    Program,
    execute_atc_with_logic_error,
)
from algosdk import constants, transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    SimulateAtomicTransactionResponse,
    TransactionWithSigner,
)
from algosdk.encoding import decode_address
from algosdk.logic import get_application_address
from algosdk.transaction import ApplicationCallTxn, ApplicationCreateTxn, OnComplete, StateSchema
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig
from nacl.signing import SigningKey

from puya.artifact_metadata import ContractState
from puya.avm import AVMType
from puya.compilation_artifacts import CompiledContract
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet

DEFAULT_MAX_OPTIMIZATION_LEVEL = int(os.getenv("MAX_TEST_OPTIMIZATION_LEVEL", "2"))
BYTES_ACTION = 1
UINT_ACTION = 2
NONE_ACTION = 3
INTC_BLOCK = 0x20
BYTEC_BLOCK = 0x26


def decode_int(result: str) -> int:
    return int.from_bytes(decode_bytes(result), byteorder="big", signed=False)


def decode_bytes(result: str) -> bytes:
    return base64.b64decode(result)


def decode_utf8(result: str) -> str:
    return decode_bytes(result).decode("utf8")


def encode_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode()


def decode_logs(logs: list[str], log_format: str) -> list[str | bytes | int]:
    assert len(logs) == len(log_format)
    result = list[str | bytes | int]()

    for fmt, log in zip(log_format, logs, strict=True):
        match fmt:
            case "i":
                result.append(decode_int(log))
            case "u":
                result.append(decode_utf8(log))
            case "b":
                result.append(decode_bytes(log))
            case _:
                raise ValueError(f"Unexpected format: {fmt}")
    return result


def encode_utf8(value: str) -> str:
    return encode_bytes(value.encode("utf8"))


@attrs.define(kw_only=True)
class Compilation:
    approval: Program
    clear: Program
    local_schema: StateSchema | None
    global_schema: StateSchema | None


def assemble_src(contract: CompiledContract, client: AlgodClient) -> Compilation:
    def state_to_schema(state: Collection[ContractState]) -> StateSchema:
        return StateSchema(
            num_uints=sum(1 for x in state if x.storage_type is AVMType.uint64),
            num_byte_slices=sum(1 for x in state if x.storage_type is AVMType.bytes),
        )

    approval_program = Program(contract.approval_program.teal_src, client)
    clear_program = Program(contract.clear_program.teal_src, client)
    compilation = Compilation(
        approval=approval_program,
        clear=clear_program,
        local_schema=state_to_schema(contract.metadata.local_state.values()),
        global_schema=state_to_schema(contract.metadata.global_state.values()),
    )
    return compilation


AppArgs: typing.TypeAlias = int | str | bytes


@attrs.frozen
class AppTransactionParameters:
    args: list[AppArgs] = attrs.field(factory=list)
    accounts: list[str] | None = None
    assets: list[int] | None = None
    on_complete: OnComplete = OnComplete.NoOpOC
    sp: transaction.SuggestedParams | None = None
    extra_pages: int | None = None
    add_random_note: bool = True


GroupTransactionsProvider: typing.TypeAlias = Callable[[int], Iterable[TransactionWithSigner]]


def _apply_all_levels(value: int | Mapping[int, int]) -> Mapping[int, int]:
    if isinstance(value, int):
        return {o: value for o in range(DEFAULT_MAX_OPTIMIZATION_LEVEL + 1)}
    else:
        return value


@attrs.frozen
class AppCallRequest(AppTransactionParameters):
    increase_budget: Mapping[int, int] = attrs.field(factory=dict, converter=_apply_all_levels)
    debug_level: int = 1
    trace_output: Path | None = None
    group_transactions: GroupTransactionsProvider | None = None

    def get_op_up_for_level(self, opt_level: int) -> int:
        return self.increase_budget.get(opt_level, 0)

    def get_trace_output_path_for_level(self, opt_level: int) -> Path | None:
        path = self.trace_output
        if path is None:
            return None
        return path.with_name(path.stem + "".join((f".O{opt_level}", *path.suffixes)))


@attrs.frozen
class AppCallResult:
    logs: list[str]
    global_state_deltas: dict[str, typing.Any]
    local_state_deltas: dict[tuple[str, str], typing.Any]
    app_id: int = attrs.field(eq=False)

    @property
    def app_address(self) -> str:
        return get_application_address(self.app_id)

    def decode_logs(self, log_format: str) -> list[str | bytes | int]:
        """
        log_format should contain a sequence of characters representing the desired types:
        b -> bytes, i -> int or u -> str
        """
        return decode_logs(self.logs, log_format)


class ATCRunner:
    def __init__(
        self,
        client: AlgodClient,
        account: Account,
        compilation: Compilation,
        op_up_app_id: int | None = None,
    ) -> None:
        self.atc = AtomicTransactionComposer()
        self.compilation = compilation
        self.sender = account.address
        self.signer = account.signer
        self.client = client
        self.op_up_app_id = op_up_app_id
        self.sp = client.suggested_params()

    def add_deployment_transaction(
        self,
        request: AppTransactionParameters,
    ) -> typing.Self:
        self.atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationCreateTxn(
                    approval_program=self.compilation.approval.raw_binary,
                    clear_program=self.compilation.clear.raw_binary,
                    local_schema=self.compilation.local_schema,
                    global_schema=self.compilation.global_schema,
                    **self._txn_args_from_request(request),
                ),
                signer=self.signer,
            )
        )
        return self

    def _txn_args_from_request(self, request: AppTransactionParameters) -> dict[str, object]:
        return {
            "sender": self.sender,
            "sp": request.sp or self.sp,
            "on_complete": request.on_complete,
            "accounts": request.accounts,
            "foreign_assets": request.assets,
            "app_args": request.args,
            "extra_pages": request.extra_pages,
            "note": random.randbytes(8) if request.add_random_note else None,
        }

    def add_transactions(
        self, *, app_id: int, get_group_transactions: GroupTransactionsProvider | None
    ) -> typing.Self:
        if get_group_transactions:
            for txn in get_group_transactions(app_id):
                self.atc.add_transaction(txn)
        return self

    def add_app_call_transaction(
        self,
        app_id: int,
        request: AppTransactionParameters,
    ) -> typing.Self:
        self.atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationCallTxn(
                    index=app_id,
                    **self._txn_args_from_request(request),
                ),
                signer=self.signer,
            )
        )
        return self

    def add_fund_transaction(self, app_id: int, micro_algos: int) -> typing.Self:
        self.atc.add_transaction(
            TransactionWithSigner(
                txn=transaction.PaymentTxn(
                    sender=self.sender,
                    receiver=get_application_address(app_id),
                    amt=micro_algos,
                    sp=self.sp,
                ),
                signer=self.signer,
            )
        )
        return self

    def add_op_ups(self, *, count: int) -> typing.Self:
        for idx in range(count):
            assert self.op_up_app_id is not None
            self.add_app_call_transaction(
                app_id=self.op_up_app_id,
                request=AppTransactionParameters(
                    args=[idx],
                    on_complete=OnComplete.NoOpOC,
                ),
            )
        return self

    def run(self, trace_path: Path | None = None) -> AppCallResult:
        if trace_path is not None:
            self._simulate_and_write_trace(trace_path)

        return self._execute_with_logic_error()

    def _simulate_and_write_trace(
        self,
        trace_path: Path,
        *,
        allow_more_logs: bool = True,
        allow_empty_signatures: bool = True,
    ) -> None:
        simulate_request = SimulateRequest(
            txn_groups=[],
            allow_more_logs=allow_more_logs,
            allow_empty_signatures=allow_empty_signatures,
            exec_trace_config=SimulateTraceConfig(
                enable=True, stack_change=True, scratch_change=True
            ),
        )
        simulate_response = self.atc.simulate(self.client, simulate_request)
        self._write_trace_to_file(simulate_response, trace_path)

    def _execute_with_logic_error(self) -> AppCallResult:
        response = execute_atc_with_logic_error(
            self.atc,
            self.client,
            self.compilation.approval.teal,
            approval_source_map=self.compilation.approval.source_map,
        )
        (txn_id, *_) = response.tx_ids
        assert response.confirmed_round, "Transaction not confirmed"
        txn_info = self.client.pending_transaction_info(txn_id)
        assert isinstance(txn_info, dict)
        app_id: int = txn_info.get("application-index", -1)
        logs = txn_info.get("logs", [])
        global_state_deltas = txn_info.get("global-state-delta", [])
        global_state_deltas_by_key = {
            delta["key"]: delta["value"] for delta in global_state_deltas
        }
        assert len(global_state_deltas) == len(global_state_deltas_by_key)
        local_state_deltas = txn_info.get("local-state-delta", [])
        local_state_deltas_by_address_and_key = {
            (account["address"], delta["key"]): delta["value"]
            for account in local_state_deltas
            for delta in account["delta"]
        }
        return AppCallResult(
            app_id=app_id,
            logs=logs,
            global_state_deltas=global_state_deltas_by_key,
            local_state_deltas=local_state_deltas_by_address_and_key,
        )

    def _write_trace_to_file(
        self,
        simulate_response: SimulateAtomicTransactionResponse,
        output_path: Path,
    ) -> None:
        def map_stack_addition(value: dict[str, typing.Any]) -> int | str:
            match value["type"]:
                case 1:
                    b64 = value.get("bytes")
                    if b64 is None:
                        return "0x"
                    try:
                        utf8 = decode_utf8(b64)
                    except UnicodeDecodeError:
                        pass
                    else:
                        if utf8.isprintable():
                            return f'"{utf8}"'
                    return "0x" + decode_bytes(b64).hex().upper()
                case 2:
                    return int(value.get("uint", 0))
                case _:
                    raise NotImplementedError(f"Mapping not implemented: {value}")

        approval_source_map = self.compilation.approval.source_map
        approval_src = self.compilation.approval.teal.splitlines()

        (txn_group,) = simulate_response.simulate_response["txn-groups"]
        txn_result, *_ = txn_group["txn-results"]
        approval_program_trace = txn_result["exec-trace"]["approval-program-trace"]

        writer = prettytable.PrettyTable(
            field_names=["PC", "Teal", "Stack"],
            header=True,
            border=False,
            padding_width=0,
            left_padding_width=0,
            right_padding_width=1,
            align="l",
        )
        stack = list[int | str]()
        for t in approval_program_trace:
            pc = t["pc"]
            teal_line = approval_source_map.get_line_for_pc(pc)
            op_code = self.compilation.approval.raw_binary[pc]
            if teal_line == 0 and op_code in (INTC_BLOCK, BYTEC_BLOCK):
                # algod collects constants and creates constant blocks for them,
                # however they do not have a corresponding teal line to map to
                # so handle that specifically
                teal = "<intcblock>" if op_code == INTC_BLOCK else "<bytecblock>"
            else:
                teal = "" if teal_line is None else approval_src[teal_line]
            teal = teal.split("//", maxsplit=1)[0].strip()
            for _ in range(t.get("stack-pop-count", 0)):
                assert stack, "Oh noes, the stack is empty, we can't pop anything"
                stack.pop()
            stack.extend(map(map_stack_addition, t.get("stack-additions", [])))

            writer.add_row(
                [
                    str(pc),
                    teal,
                    ", ".join(map(str, stack)),
                ]
            )
        output_path.write_text(writer.get_string(), encoding="utf8")


@attrs.define
class _TestHarness:
    client: AlgodClient = attrs.field(on_setattr=attrs.setters.frozen)
    account: Account = attrs.field(on_setattr=attrs.setters.frozen)
    op_up_app_id: int = attrs.field(on_setattr=attrs.setters.frozen)
    max_optimization_level: int = attrs.field(
        default=DEFAULT_MAX_OPTIMIZATION_LEVEL, on_setattr=attrs.setters.frozen
    )
    _app_ids_by_level: dict[int, int] = attrs.field(factory=dict, init=False)
    _compilations_by_level: dict[int, Compilation] = attrs.field(factory=dict, init=False)

    @property
    def sender(self) -> str:
        return self.account.address

    @property
    def _optimization_levels(self) -> range:
        return range(self.max_optimization_level + 1)

    def deploy_from_closure(
        self,
        closure: typing.Callable[[], None],
        request: AppCallRequest | None = None,
    ) -> AppCallResult:
        with TemporaryDirectory() as tmp_dir:
            src_path = Path(tmp_dir) / "contract.py"
            source = inspect.getsource(closure)
            closure_lines = source.splitlines()[1:]
            closure_text_block = dedent("\n".join(closure_lines))
            src_path.write_text(closure_text_block, encoding="utf8")
            return self.deploy(src_path, request)

    def deploy(
        self,
        src_path: Path,
        request: AppCallRequest | None = None,
    ) -> AppCallResult:
        if request is None:
            request = AppCallRequest()

        self._compilations_by_level = {
            o_level: self._compile_and_assemble_src(
                src_path, optimization_level=o_level, debug_level=request.debug_level
            )
            for o_level in self._optimization_levels
        }

        o_level_deploy_results = {
            o_level: (
                self._new_runner(compilation)
                .add_transactions(app_id=0, get_group_transactions=request.group_transactions)
                .add_deployment_transaction(request)
                .add_op_ups(count=request.get_op_up_for_level(o_level))
                .run(trace_path=request.get_trace_output_path_for_level(o_level))
            )
            for o_level, compilation in self._compilations_by_level.items()
        }
        self._app_ids_by_level = {
            o_level: deploy_result.app_id
            for o_level, deploy_result in o_level_deploy_results.items()
        }
        return self._get_singularly_valid_result(o_level_deploy_results)

    def fund(self, micro_algos: int) -> None:
        for o_level, compilation in self._compilations_by_level.items():
            (
                self._new_runner(compilation)
                .add_fund_transaction(
                    app_id=self._app_ids_by_level[o_level],
                    micro_algos=micro_algos,
                )
                .run()
            )

    def call(self, request: AppCallRequest) -> AppCallResult:
        o_level_results = {
            o_level: (
                self._new_runner(compilation)
                .add_transactions(
                    app_id=self._app_ids_by_level[o_level],
                    get_group_transactions=request.group_transactions,
                )
                .add_app_call_transaction(
                    app_id=self._app_ids_by_level[o_level],
                    request=request,
                )
                .add_op_ups(count=request.get_op_up_for_level(o_level))
                .run(trace_path=request.get_trace_output_path_for_level(o_level))
            )
            for o_level, compilation in self._compilations_by_level.items()
        }
        return self._get_singularly_valid_result(o_level_results)

    def _get_singularly_valid_result(
        self, results_by_level: dict[int, AppCallResult]
    ) -> AppCallResult:
        # this might seem a bit weird, but it's to get the most comprehensive output possible
        first_result, *_ = results_by_level.values()
        assert results_by_level == {o: first_result for o in self._optimization_levels}
        return first_result

    def _new_runner(self, compilation: Compilation) -> ATCRunner:
        return ATCRunner(
            client=self.client,
            account=self.account,
            compilation=compilation,
            op_up_app_id=self.op_up_app_id,
        )

    def _compile_and_assemble_src(
        self, src_path: Path, optimization_level: int, debug_level: int
    ) -> Compilation:
        result = compile_src_from_options(
            PuyaPyOptions(
                paths=(src_path,),
                optimization_level=optimization_level,
                debug_level=debug_level,
            )
        )
        (contract,) = result.teal
        assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"

        return assemble_src(contract=contract, client=self.client)


@pytest.fixture(scope="session")
def no_op_app_id(algod_client: AlgodClient, account: Account, worker_id: str) -> int:
    program = Program("#pragma version 8\npushint 1", algod_client)
    compilation = Compilation(
        approval=program, clear=program, global_schema=None, local_schema=None
    )
    result = (
        ATCRunner(client=algod_client, account=account, compilation=compilation)
        .add_deployment_transaction(
            AppTransactionParameters(
                args=[worker_id],  # this ensures a unique instance per parallel test run
            ),
        )
        .run()
    )
    return result.app_id


@pytest.fixture
def harness(algod_client: AlgodClient, account: Account, no_op_app_id: int) -> _TestHarness:
    return _TestHarness(algod_client, account, op_up_app_id=no_op_app_id)


def test_ssa(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "ssa",
        AppCallRequest(trace_output=TEST_CASES_DIR / "ssa" / "out" / "trace.log"),
    )

    assert result.decode_logs("i") == [102]


def test_tuple_support(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "tuple_support" / "tuple_support.py")
    assert result.decode_logs("iuiiiuuuuu") == [
        306,
        "Hello, world!",
        0,
        2,
        1,
        "nanananana",
        "non_empty_tuple called",
        "not empty",
        "get_uint_with_side_effect called",
        "not empty2",
    ]


def test_tuple_comparisons(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "tuple_support" / "tuple_comparisons.py")
    expected_log_values = list(range(42, 48))
    assert len(result.logs) == len(expected_log_values)
    assert result.decode_logs("i" * len(expected_log_values)) == expected_log_values


def test_chained_assignment(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "chained_assignment")
    assert result.decode_logs("u") == ["Hello, world! 👋"]


def test_callsub(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "callsub")
    assert result.decode_logs("iii") == [42, 1, 2]


def test_calculator(harness: _TestHarness) -> None:
    src_path = EXAMPLES_DIR / "calculator"
    add, sub, mul, div = 1, 2, 3, 4

    result = harness.deploy(src_path, AppCallRequest(args=[add, 1, 2]))
    assert result.decode_logs("iiu") == [1, 2, "1 + 2 = 3"]

    result = harness.deploy(src_path, AppCallRequest(args=[sub, 45, 2]))
    assert result.decode_logs("iiu") == [45, 2, "45 - 2 = 43"]

    result = harness.deploy(src_path, AppCallRequest(args=[mul, 42, 42]))
    assert result.decode_logs("iiu") == [42, 42, "42 * 42 = 1764"]

    result = harness.deploy(src_path, AppCallRequest(args=[div, 8, 2]))
    assert result.decode_logs("iiu") == [8, 2, "8 // 2 = 4"]

    with pytest.raises(algokit_utils.LogicError):
        harness.deploy(src_path)

    with pytest.raises(algokit_utils.LogicError):
        harness.deploy(src_path, AppCallRequest(args=[9, 20, 8]))


def test_subroutine_parameter_overwrite(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Bytes, Contract, log, op, subroutine

        class Exclaimer(Contract):
            def approval_program(self) -> bool:
                num_args = op.Txn.num_app_args
                assert num_args == 1, "expected one arg"
                msg = op.Txn.application_args(0)
                exclaimed = self.exclaim(msg)
                log(exclaimed)
                return True

            @subroutine
            def exclaim(self, value: Bytes) -> Bytes:
                value = value + b"!"
                return value

            def clear_state_program(self) -> bool:
                return True

    result = harness.deploy_from_closure(test, AppCallRequest(args=[b"whoop"]))
    assert result.decode_logs("u") == ["whoop!"]


def test_nested_loops(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "nested_loops", AppCallRequest(increase_budget=15))
    x, y = result.decode_logs("ii")
    assert x == 192
    assert y == 285


def test_with_reentrancy(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "with_reentrancy")
    logs = result.decode_logs("iuuuuuu")
    assert logs == [
        5,
        "silly3 = 8",
        "silly2 = 8",
        "silly = 6",
        "silly3 = 5",
        "silly2 = 5",
        "silly = 3",
    ]


def test_conditional_expressions(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "conditional_expressions" / "contract.py")
    logs = result.decode_logs(("u" * 6) + "i")
    counts = collections.Counter(logs[:-1])
    assert counts == {
        "expensive_op": 3,
        "side_effecting_op": 3,
    }
    assert logs[-1] == 19


def test_literal_conditional_expressions(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "conditional_expressions" / "literals.py")


def test_contains_operator(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "contains", request=AppCallRequest(increase_budget=1))


def test_boolean_binary_ops(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "boolean_binary_ops", request=AppCallRequest(increase_budget=1)
    )
    logs = set(result.decode_logs("u" * 12))
    assert logs == {
        # AND
        "lhs_true_and_true",
        "rhs_true_and_true",
        "lhs_true_and_false",
        "rhs_true_and_false",
        "lhs_false_and_true",
        # "rhs_false_and_true",
        "lhs_false_and_false",
        # "rhs_false_and_false",
        # OR
        "lhs_true_or_true",
        # "rhs_true_or_true",
        "lhs_true_or_false",
        # "rhs_true_or_false",
        "lhs_false_or_true",
        "rhs_false_or_true",
        "lhs_false_or_false",
        "rhs_false_or_false",
    }


def test_biguint_binary_ops(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "biguint_binary_ops")


def test_unssa(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "unssa",
        AppCallRequest(
            increase_budget=1,
            trace_output=TEST_CASES_DIR / "unssa" / "out" / "execution_trace.log",
        ),
    )
    result1, result2 = result.decode_logs("ii")
    assert result1 == 2
    assert result2 == 1


def test_byte_constants(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "constants" / "byte_constants.py")
    the_str, the_length = result.decode_logs("bi")
    expected = b"Base 16 encoded|Base 64 encoded|Base 32 encoded|UTF-8 Encoded"
    assert the_str == expected
    assert the_length == len(expected)


def test_bytes_ops(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "bytes_ops")


def test_simplish(harness: _TestHarness) -> None:
    nickname = "My Nicky Nick"
    harness.deploy(TEST_CASES_DIR / "simplish")

    opt_in_result = harness.call(AppCallRequest(args=[nickname], on_complete=OnComplete.OptInOC))
    assert not opt_in_result.logs
    assert opt_in_result.local_state_deltas == {
        (harness.sender, encode_utf8("name")): {
            "action": 1,
            "bytes": encode_utf8(nickname),
        },
    }
    assert not opt_in_result.global_state_deltas

    circle_report_result = harness.call(AppCallRequest(args=["circle_report", 123]))
    assert circle_report_result.decode_logs("uu") == [
        "Approximate area and circumference of circle with radius 123 = 47529, 772",
        "Incrementing counter!",
    ]
    assert not circle_report_result.local_state_deltas
    assert circle_report_result.global_state_deltas == {
        encode_utf8("counter"): {
            "action": 2,
            "uint": 1,
        }
    }

    delete_result = harness.call(AppCallRequest(on_complete=OnComplete.DeleteApplicationOC))
    assert delete_result.decode_logs("u") == ["I was used 1 time(s) before I died"]
    assert not delete_result.global_state_deltas
    assert not delete_result.local_state_deltas


def test_address(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "constants" / "address_constant.py")
    sender_bytes = decode_address(harness.sender)
    assert result.decode_logs("b") == [sender_bytes]


def test_string_ops(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "string_ops", AppCallRequest(increase_budget=4))


def test_global_storage(harness: _TestHarness) -> None:
    harness.deploy(EXAMPLES_DIR / "global_state", AppCallRequest(increase_budget=1))


def test_local_storage(harness: _TestHarness) -> None:
    default_value = "this is a default"
    stored_value = "testing 123"
    harness.deploy(
        EXAMPLES_DIR / "local_state/local_state_contract.py",
        AppCallRequest(on_complete=OnComplete.OptInOC),
    )

    get_data_with_default_result_1 = harness.call(
        AppCallRequest(args=["get_data_with_default", default_value])
    )
    assert get_data_with_default_result_1.decode_logs("u") == [default_value]

    set_data_result = harness.call(AppCallRequest(args=["set_data", stored_value]))
    assert set_data_result.local_state_deltas == {
        (harness.sender, encode_utf8("local")): {
            "action": 1,
            "bytes": encode_utf8(stored_value),
        }
    }

    get_data_with_default_result_2 = harness.call(
        AppCallRequest(args=["get_data_with_default", default_value])
    )
    assert get_data_with_default_result_2.decode_logs("u") == [stored_value]

    get_guaranteed_data_result = harness.call(AppCallRequest(args=["get_guaranteed_data"]))
    assert get_guaranteed_data_result.decode_logs("u") == [stored_value]

    get_data_or_assert_result = harness.call(AppCallRequest(args=["get_data_or_assert"]))
    assert get_data_or_assert_result.decode_logs("u") == [stored_value]

    delete_data_result = harness.call(AppCallRequest(args=["delete_data"]))
    assert delete_data_result.local_state_deltas == {
        (harness.sender, encode_utf8("local")): {"action": 3}
    }


def test_local_storage_with_offsets(harness: _TestHarness) -> None:
    default_value = "this is a default"
    stored_value = "testing 123"
    harness.deploy(
        EXAMPLES_DIR / "local_state/local_state_with_offsets.py",
        AppCallRequest(on_complete=OnComplete.OptInOC),
    )

    def make_request(*args: AppArgs) -> AppCallRequest:
        return AppCallRequest(
            # yes this is redundant, sender is [0] anyway
            args=[1, *args],
            accounts=[harness.sender],
        )

    get_data_with_default_result_1 = harness.call(
        make_request("get_data_with_default", default_value)
    )
    assert get_data_with_default_result_1.decode_logs("u") == [default_value]

    set_data_result = harness.call(make_request("set_data", stored_value))
    assert set_data_result.local_state_deltas == {
        (harness.sender, encode_utf8("local")): {
            "action": 1,
            "bytes": encode_utf8(stored_value),
        }
    }

    get_data_with_default_result_2 = harness.call(
        make_request("get_data_with_default", default_value)
    )
    assert get_data_with_default_result_2.decode_logs("u") == [stored_value]

    get_guaranteed_data_result = harness.call(make_request("get_guaranteed_data"))
    assert get_guaranteed_data_result.decode_logs("u") == [stored_value]

    get_data_or_assert_result = harness.call(make_request("get_data_or_assert"))
    assert get_data_or_assert_result.decode_logs("u") == [stored_value]

    delete_data_result = harness.call(make_request("delete_data"))
    assert delete_data_result.local_state_deltas == {
        (harness.sender, encode_utf8("local")): {"action": 3}
    }


def test_unary(harness: _TestHarness) -> None:
    unary_path = TEST_CASES_DIR / "unary"
    harness.deploy(
        unary_path,
        AppCallRequest(trace_output=unary_path / "out" / "execution_trace.log"),
    )


def test_enumeration(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "enumeration", AppCallRequest(increase_budget=1))


def test_scratch_slots(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "scratch_slots" / "contract.py", AppCallRequest())


def test_scratch_slots_inheritance(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "scratch_slots" / "contract2.py", AppCallRequest())


def test_bytes_stubs(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "stubs" / "bytes.py",
        AppCallRequest(
            increase_budget=1, trace_output=TEST_CASES_DIR / "stubs" / "out" / "bytes.log"
        ),
    )
    assert result.decode_logs("u") == ["one_to_seven called"]


def test_uint64_stubs(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "stubs" / "uint64.py", AppCallRequest(increase_budget=1))


def test_string_stubs(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "stubs" / "string.py", AppCallRequest(increase_budget=2))


def test_biguint_stubs(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "stubs" / "biguint.py", AppCallRequest(increase_budget=1))


def test_biguint_from_to_bytes(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import BigUInt, Contract, log, op

        class BigUIntByteTests(Contract):
            def approval_program(self) -> bool:
                arg = op.Txn.application_args(0)
                big_uint = BigUInt.from_bytes(arg)
                big_uint += 1
                log(big_uint.bytes)
                return True

            def clear_state_program(self) -> bool:
                return True

    result = harness.deploy_from_closure(test, AppCallRequest(args=[122]))
    assert result.decode_logs("i") == [123]


def test_abi_string(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "string.py",
        AppCallRequest(trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "string.log"),
    )


def test_abi_reference_types(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "arc4_types" / "reference_types.py")


def test_abi_numeric(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "numeric.py",
        AppCallRequest(trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "numeric.log"),
    )


def test_abi_array(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "array.py",
        AppCallRequest(
            trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "array.log", increase_budget=1
        ),
    )


def test_dynamic_bytes(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "arc4_types" / "dynamic_bytes.py")


def test_abi_bool(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "bool.py",
        AppCallRequest(trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "bool.log"),
    )


def test_abi_tuple(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "tuples.py",
        AppCallRequest(
            trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "tuples.log",
            increase_budget={0: 1},
        ),
    )


def test_abi_struct(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "structs.py",
        AppCallRequest(trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "structs.log"),
    )
    x, y, z = result.decode_logs("bbb")

    assert x == 0x1079F7E42E.to_bytes(8, "big")
    assert y == 0x4607097084.to_bytes(8, "big")
    assert z == 0b10100000.to_bytes()


def test_abi_mutations(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "mutation.py",
        AppCallRequest(
            extra_pages=1,
            trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "mutation.log",
            increase_budget=15,
        ),
    )


def test_abi_mutable_params(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "mutable_params.py",
        AppCallRequest(
            extra_pages=1,
            trace_output=TEST_CASES_DIR / "arc4_types" / "out" / "mutable_params.log",
            increase_budget=2,
        ),
    )


def test_abi_bool_eval(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_types" / "bool_eval.py",
        AppCallRequest(extra_pages=1),
    )


def test_arc4_uintn_comparisons(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "arc4_numeric_comparisons" / "uint_n.py",
        AppCallRequest(increase_budget=1),
    )


@pytest.mark.parametrize(
    ("test_case", "expected_logic_error"),
    [
        (b"uint", "+ arg 0 wanted uint64 but got []byte"),
        (b"bytes", "b+ arg 0 wanted bigint but got uint64"),
        (b"mixed", "itob arg 0 wanted uint64 but got []byte"),
    ],
)
def test_undefined_phi_args(
    harness: _TestHarness, test_case: bytes, expected_logic_error: str
) -> None:
    example = TEST_CASES_DIR / "undefined_phi_args"
    harness.deploy(example, AppCallRequest(args=[test_case]))

    with pytest.raises(LogicError) as ex_info:
        harness.deploy(example, AppCallRequest(args=[test_case, True], debug_level=2))
    ex = ex_info.value
    assert ex.message == expected_logic_error
    assert ex.line_no is not None
    assert "💥" in "".join(ex.lines[ex.line_no - 5 : ex.line_no])


def test_augmented_assignment(harness: _TestHarness) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "augmented_assignment" / "contract.py",
        AppCallRequest(args=[0], on_complete=OnComplete.OptInOC),
    )

    assert result.global_state_deltas == {
        encode_utf8("counter"): {
            "action": UINT_ACTION,
        },
        encode_utf8("global_uint"): {
            "action": UINT_ACTION,
        },
        encode_utf8("global_bytes"): {
            "action": BYTES_ACTION,
        },
    }
    assert result.local_state_deltas == {
        (harness.account.address, encode_utf8("my_uint")): {
            "action": UINT_ACTION,
        },
        (harness.account.address, encode_utf8("my_bytes")): {
            "action": BYTES_ACTION,
        },
    }

    args: list[int | str | bytes] = [0]
    result = harness.call(AppCallRequest(args=args))
    increment_uint = len(args)
    expected_uint = increment_uint
    expected_bytes = increment_uint.to_bytes(byteorder="big", length=8)
    assert result.global_state_deltas == {
        encode_utf8("counter"): {
            "action": UINT_ACTION,
            "uint": 2,
        },
        encode_utf8("global_uint"): {
            "action": UINT_ACTION,
            "uint": expected_uint,
        },
        encode_utf8("global_bytes"): {
            "action": BYTES_ACTION,
            "bytes": encode_bytes(expected_bytes),
        },
    }

    assert result.local_state_deltas == {
        (harness.account.address, encode_utf8("my_uint")): {
            "action": UINT_ACTION,
            "uint": expected_uint,
        },
        (harness.account.address, encode_utf8("my_bytes")): {
            "action": BYTES_ACTION,
            "bytes": encode_bytes(expected_bytes),
        },
    }

    args = [0, 1]
    result = harness.call(AppCallRequest(args=args))
    increment_uint = len(args)
    expected_uint += increment_uint
    expected_bytes += increment_uint.to_bytes(byteorder="big", length=8)
    assert result.global_state_deltas == {
        encode_utf8("counter"): {
            "action": UINT_ACTION,
            "uint": 2,
        },
        encode_utf8("global_uint"): {
            "action": UINT_ACTION,
            "uint": expected_uint,
        },
        encode_utf8("global_bytes"): {
            "action": BYTES_ACTION,
            "bytes": encode_bytes(expected_bytes),
        },
    }

    assert result.local_state_deltas == {
        (harness.account.address, encode_utf8("my_uint")): {
            "action": UINT_ACTION,
            "uint": expected_uint,
        },
        (harness.account.address, encode_utf8("my_bytes")): {
            "action": BYTES_ACTION,
            "bytes": encode_bytes(expected_bytes),
        },
    }


def test_asset(harness: _TestHarness, asset_a: int, asset_b: int) -> None:
    harness.deploy(TEST_CASES_DIR / "asset")

    # ensure app meets minimum balance requirements
    harness.fund(200_000)

    # increase fee to cover opt_in inner txn
    increased_fee = harness.client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 2

    # call functions to assert asset behaviour
    harness.call(AppCallRequest(args=[b"opt_in"], assets=[asset_a], sp=increased_fee))
    harness.call(AppCallRequest(args=[b"is_opted_in"], assets=[asset_a]))
    with pytest.raises(LogicError, match=re.escape("asset self.asa == asset")):
        harness.call(AppCallRequest(args=[b"is_opted_in"], assets=[asset_b]))


def test_verify(harness: _TestHarness) -> None:
    key = SigningKey.generate()
    data = b"random bytes"
    sig = key.sign(data).signature
    public_key = key.verify_key.encode()

    result = harness.deploy(
        TEST_CASES_DIR / "edverify",
        AppCallRequest(
            args=[data, sig, public_key],
            increase_budget=4,
        ),
    )
    (verify_outcome,) = result.decode_logs("i")

    assert verify_outcome == 1


def test_application(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "application")

    harness.call(AppCallRequest(args=[b"validate"]))


def test_conditional_execution(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "conditional_execution",
        request=AppCallRequest(
            trace_output=TEST_CASES_DIR / "conditional_execution" / "out" / "trace.log",
        ),
    )


def iteration_idfn(value: object) -> str:
    if isinstance(value, str):
        return value
    else:
        return ""


_test_iteration_params = [("tuple", 0), ("indexable", 0), ("urange", 1)]


@pytest.mark.parametrize(
    ("name", "increase_budget"), _test_iteration_params, ids=[p[0] for p in _test_iteration_params]
)
def test_iteration(harness: _TestHarness, name: str, increase_budget: int) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "iteration" / f"iterate_{name}.py",
        AppCallRequest(increase_budget=increase_budget),
    )
    expected_logs = [
        "test_forwards",
        "a",
        "b",
        "c",
        "test_reversed",
        "c",
        "b",
        "a",
        "test_forwards_with_forwards_index",
        "0=a",
        "1=b",
        "2=c",
        "test_forwards_with_reverse_index",
        "2=a",
        "1=b",
        "0=c",
        "test_reverse_with_forwards_index",
        "0=c",
        "1=b",
        "2=a",
        "test_reverse_with_reverse_index",
        "2=c",
        "1=b",
        "0=a",
        "test_empty",
        "test_break",
        "a",
        "test_tuple_target",
        "0=t",
    ]
    assert len(result.logs) == len(expected_logs)
    logs_decoded = result.decode_logs(len(expected_logs) * "u")
    assert logs_decoded == expected_logs


def test_ignored_value(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Contract, subroutine

        class Silly(Contract):
            def approval_program(self) -> bool:
                True  # noqa: B018
                self.silly()
                return True

            @subroutine
            def silly(self) -> bool:
                True  # noqa: B018
                return True

            def clear_state_program(self) -> bool:
                return True

    harness.deploy_from_closure(test)


def test_intrinsics_immediate_variants(harness: _TestHarness) -> None:
    sp = harness.client.suggested_params()
    sp.fee = 10
    harness.deploy(
        TEST_CASES_DIR / "intrinsics" / "immediate_variants.py",
        AppCallRequest(args=[b""], sp=sp, add_random_note=True),
    )


def test_intrinsics_overloaded(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "intrinsics" / "overloaded.py")


def test_too_many_permutations(harness: _TestHarness) -> None:
    harness.deploy(
        TEST_CASES_DIR / "too_many_permutations",
        request=AppCallRequest(args=[1, 2, 3, 4]),
    )


@pytest.mark.parametrize(
    ("args", "expected_logs"),
    [
        ([], []),
        ([1], [1]),
        ([1, 2], []),
        ([1, 2, 3], [3]),
    ],
)
def test_control_op_simplification(
    harness: _TestHarness, args: list[int], expected_logs: list[int]
) -> None:
    result = harness.deploy(
        TEST_CASES_DIR / "control_op_simplification", request=AppCallRequest(args=[*args])
    )
    assert result.decode_logs("i" * len(expected_logs)) == expected_logs


def test_log(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "log")
    u64_bytes = [x.to_bytes(length=8) for x in range(8)]
    bytes_8 = b"\x08"
    assert result.decode_logs("b" * 8) == [
        u64_bytes[0],
        b"1",
        b"2",
        u64_bytes[3],
        b"",
        b"5" + u64_bytes[6] + u64_bytes[7] + bytes_8 + b"",
        b"_".join((b"5", u64_bytes[6], u64_bytes[7], bytes_8, b"")),
        b"_".join((b"5", u64_bytes[6], u64_bytes[7], bytes_8, b"")),
    ]


def test_inner_transactions(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "inner_transactions" / "contract.py")
    # ensure app meets minimum balance requirements
    harness.fund(9 * 100_000)

    increased_fee = harness.client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * (1 + 16)

    harness.call(AppCallRequest(sp=increased_fee, args=[b"test1"]))

    harness.call(AppCallRequest(sp=increased_fee, args=[b"test2"]))

    harness.call(AppCallRequest(sp=increased_fee, args=[b"test2", b"do 2nd submit"]))

    harness.call(AppCallRequest(sp=increased_fee, args=[b"test3"]))

    harness.call(AppCallRequest(sp=increased_fee, args=[b"test4"]))


def test_inner_transactions_loop(harness: _TestHarness) -> None:
    increased_fee = harness.client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * (1 + 4)

    result = harness.deploy(
        TEST_CASES_DIR / "inner_transactions" / "itxn_loop.py",
        AppCallRequest(
            sp=increased_fee,
            add_random_note=True,
        ),
    )

    assert result.decode_logs("bibibibi") == [b"", 0, b"A", 1, b"AB", 2, b"ABC", 3]


def test_inheritance_direct_method_invocation(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "inheritance" / "child.py")
    assert result.decode_logs("uu") == [
        "ChildContract.method called",
        "GrandParentContract.method called",
    ]


def test_account_from_bytes_validation(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Account, Contract, Txn

        class Baddie(Contract):
            def approval_program(self) -> bool:
                b = Txn.sender.bytes + b"!"
                x = Account(b)
                assert x.bytes.length > 0, "shouldn't get here"
                return True

            def clear_state_program(self) -> bool:
                return True

    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        harness.deploy_from_closure(test)
    assert exc_info.value.line_no is not None
    assert "// Address length is 32 bytes" in exc_info.value.lines[exc_info.value.line_no]


def test_arc4_address_from_bytes_validation(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Contract, Txn, arc4

        class Baddie(Contract):
            def approval_program(self) -> bool:
                b = Txn.sender.bytes + b"!"
                x = arc4.Address(b)
                assert x.bytes.length > 0, "shouldn't get here"
                return True

            def clear_state_program(self) -> bool:
                return True

    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        harness.deploy_from_closure(test)
    assert exc_info.value.line_no is not None
    assert "// Address length is 32 bytes" in exc_info.value.lines[exc_info.value.line_no]


def test_tuple_element_mutation(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Contract, arc4

        class MyContract(Contract):
            def approval_program(self) -> bool:
                t = (arc4.UInt64(1), arc4.DynamicBytes(b"abc"))
                assert t[1].bytes[2:] == b"abc", "initial value"
                t[1].extend(arc4.DynamicBytes(b"def"))
                assert t[1].bytes[2:] == b"abcdef", "updated value"
                return True

            def clear_state_program(self) -> bool:
                return True

    harness.deploy_from_closure(test)


def test_arc4_tuple_element_mutation(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import Contract, arc4

        class MyContract(Contract):
            def approval_program(self) -> bool:
                t = arc4.Tuple((arc4.UInt64(1), arc4.DynamicBytes(b"abc")))
                assert t[1].bytes[2:] == b"abc", "initial value"
                t[1].extend(arc4.DynamicBytes(b"def"))
                assert t[1].bytes[2:] == b"abcdef", "updated value"
                return True

            def clear_state_program(self) -> bool:
                return True

    harness.deploy_from_closure(test)


def test_arc4_copy_in_state(harness: _TestHarness) -> None:
    def test() -> None:
        from algopy import GlobalState, arc4

        class MyContract(arc4.ARC4Contract):
            def __init__(self) -> None:
                self.g = GlobalState(arc4.Address())

            @arc4.abimethod
            def okay(self) -> None:
                pass

    harness.deploy_from_closure(test)


@pytest.mark.slow
def test_brute_force_rotation_search(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "stress_tests" / "brute_force_rotation_search.py")


def test_match(harness: _TestHarness) -> None:
    result = harness.deploy(TEST_CASES_DIR / "match" / "contract.py", AppCallRequest(args=[b""]))
    assert result.decode_logs(4 * "u") == [
        "Hello There biguint",
        "Hello bytes",
        "Hello one",
        "Hello True",
    ]


def test_loop_else(harness: _TestHarness) -> None:
    contract_path = TEST_CASES_DIR / "loop_else" / "loop_else.py"
    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        harness.deploy(contract_path, AppCallRequest(args=[0, 1]))
    assert exc_info.value.message == "err opcode executed"
    assert exc_info.value.line_no is not None
    assert (
        "// access denied, missing secret argument" in exc_info.value.lines[exc_info.value.line_no]
    )

    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        harness.deploy(contract_path, AppCallRequest(args=[2, b"while_secret", 3]))
    assert exc_info.value.message == "err opcode executed"
    assert exc_info.value.line_no is not None
    assert (
        "// access denied, missing secret account" in exc_info.value.lines[exc_info.value.line_no]
    )

    with_all_secrets_result = harness.deploy(
        contract_path,
        AppCallRequest(
            args=[4, b"while_secret", 5],
            accounts=[algosdk.constants.ZERO_ADDRESS, harness.account.address],
        ),
    )
    assert with_all_secrets_result.decode_logs("u") == [
        "found secret argument at idx=1 and secret account at idx=1"
    ]


def test_regression_194(harness: _TestHarness) -> None:
    harness.deploy(TEST_CASES_DIR / "regression_tests" / "issue_194.py")
