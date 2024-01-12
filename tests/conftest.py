import functools
import tempfile
import typing
from collections.abc import Iterable
from pathlib import Path

import attrs
import pytest
import structlog.testing
from algokit_utils import (
    Account,
    get_algod_client,
    get_default_localnet_config,
    get_localnet_default_account,
)
from algosdk import transaction
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner
from algosdk.v2client.algod import AlgodClient
from puya.awst.nodes import Module
from puya.awst_build.main import transform_ast
from puya.codegen.emitprogram import CompiledContract
from puya.compile import awst_to_teal, parse_with_mypy, write_teal_to_output
from puya.context import CompileContext
from puya.errors import Errors
from puya.logging_config import LogLevel, configure_logging
from puya.options import PuyaOptions
from puya.parse import ParseSource, SourceLocation, get_parse_sources
from puya.utils import pushd

VCS_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = VCS_ROOT / "examples"
TEST_CASES_DIR = VCS_ROOT / "test_cases"
APPROVAL_EXTENSIONS = ("*.teal", "*.awst", "*.ir")


@pytest.fixture(autouse=True, scope="session")
def _setup_logging() -> None:
    # configure logging for tests
    # note cache_logger should be False if calling configure_logging more than once
    configure_logging(min_log_level=LogLevel.info, cache_logger=False)


@pytest.fixture(scope="session")
def algod_client() -> AlgodClient:
    return get_algod_client(get_default_localnet_config("algod"))


@pytest.fixture(scope="session")
def account(algod_client: AlgodClient) -> Account:
    return get_localnet_default_account(algod_client)


@pytest.fixture(scope="session")
def asset_a(algod_client: AlgodClient, account: Account) -> int:
    return create_asset(algod_client, account, "a")


@pytest.fixture(scope="session")
def asset_b(algod_client: AlgodClient, account: Account) -> int:
    return create_asset(algod_client, account, "b")


def create_asset(algod_client: AlgodClient, account: Account, asset_unit: str) -> int:
    sp = algod_client.suggested_params()
    atc = AtomicTransactionComposer()
    atc.add_transaction(
        TransactionWithSigner(
            transaction.AssetCreateTxn(
                account.address,
                sp,
                10_000_000,
                0,
                default_frozen=False,
                asset_name=f"asset {asset_unit}",
                unit_name=asset_unit,
            ),
            signer=account.signer,
        )
    )
    response = atc.execute(algod_client, 4)
    txn_id = response.tx_ids[0]
    result = algod_client.pending_transaction_info(txn_id)
    assert isinstance(result, dict)
    asset_index = result["asset-index"]
    assert isinstance(asset_index, int)
    return asset_index


def _get_root_dir(path: Path) -> Path | None:
    if path.is_relative_to(EXAMPLES_DIR):
        return EXAMPLES_DIR
    elif path.is_relative_to(TEST_CASES_DIR):
        return TEST_CASES_DIR
    return None


@attrs.define
class CompileCache:
    context: CompileContext
    module_awst: dict[str, Module]
    logs: list[structlog.typing.EventDict]


@functools.cache
def _get_awst_cache(root_dir: Path) -> CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with structlog.testing.capture_logs() as logs:
        context = parse_with_mypy(PuyaOptions(paths=[root_dir]))
        awst = transform_ast(context)
        return CompileCache(context, awst, logs)


def parse_src_to_awst(src_path: Path) -> CompileCache:
    root_dir = _get_root_dir(src_path)

    if root_dir is None:
        compile_cache = _get_awst_cache(src_path)
    else:
        with pushd(root_dir):
            compile_cache = _get_awst_cache(root_dir)

    # create a new context from cache and specified src
    context = compile_cache.context
    module_awst = compile_cache.module_awst
    logs = compile_cache.logs
    sources = get_parse_sources(
        [src_path], context.parse_result.manager.fscache, context.parse_result.manager.options
    )
    # create a new context from the cache
    context = attrs.evolve(
        compile_cache.context,
        errors=Errors(),
        parse_result=attrs.evolve(context.parse_result, sources=sources),
    )
    return CompileCache(context, module_awst, logs)


@attrs.define
class CompileContractResult:
    context: CompileContext
    module_awst: dict[str, Module]
    logs: str
    teal: dict[ParseSource, list[CompiledContract]]
    output_files: dict[str, str]


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _stabilise_logs(
    logs: list[structlog.typing.EventDict], root_dir: Path, tmp_dir: Path, actual_path: Path
) -> Iterable[str]:
    normalized_vcs = _normalize_path(VCS_ROOT)
    normalized_tmp = _normalize_path(tmp_dir)
    normalized_root = _normalize_path(root_dir) + "/"
    actual_dir = actual_path if actual_path.is_dir() else actual_path.parent
    normalized_out = _normalize_path(actual_dir / "out")
    normalized_relative = _normalize_path(actual_path.relative_to(root_dir))
    for log in logs:
        location = ""
        try:
            src_location = log["location"]
            assert isinstance(src_location, SourceLocation)
            path = Path(src_location.file)
            if not path.is_relative_to(root_dir):
                continue
            location = str(path.relative_to(root_dir))
            if not location.startswith(normalized_relative):
                continue
            location = f"{location}:{src_location.line} "
        except KeyError:
            pass
        msg: str = log["event"]
        line = f"{location}{log['log_level']}: {msg}"
        line = line.replace("\\", "/")
        line = line.replace(normalized_tmp, normalized_out)
        line = line.replace(normalized_root, "")
        line = line.replace(normalized_vcs, "<git root>")

        if not line.startswith(
            (
                "debug: Building AWST for ",
                "debug: Skipping puyapy stub ",
                "debug: Skipping typeshed stub ",
                "warning: Skipping stub: ",
                "debug: Skipping stdlib stub ",
            )
        ):
            yield line


class CompileSrc(typing.Protocol):
    def __call__(
        self, src_path: Path, optimization_level: int, debug_level: int
    ) -> CompileContractResult:
        ...


@functools.cache
def compile_src(
    src_path: Path, optimization_level: int, debug_level: int
) -> CompileContractResult:
    compile_cache = parse_src_to_awst(src_path)
    context = compile_cache.context
    awst = compile_cache.module_awst
    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            options=PuyaOptions(
                paths=(src_path,),
                optimization_level=optimization_level,
                debug_level=debug_level,
                output_teal=True,
                output_awst=True,
                output_final_ir=True,
                output_arc32=True,
                output_ssa_ir=True,
                output_optimization_ir=True,
                output_cssa_ir=True,
                output_post_ssa_ir=True,
                output_parallel_copies_ir=True,
                out_dir=Path(tmp_dir),
            ),
        )
        root_dir = _get_root_dir(src_path) or Path.cwd()
        with pushd(root_dir), structlog.testing.capture_logs() as logs:
            teal = awst_to_teal(context, awst)
            assert teal is not None, f"compilation failed: {src_path} at O{optimization_level}"
            write_teal_to_output(context, teal)

        output_files = {}
        for ext in APPROVAL_EXTENSIONS:
            for file in tmp_dir.rglob(ext):
                output_files[file.name] = file.read_text("utf8")
        assert teal is not None, "compile error"
        log_txt = "\n".join(
            _stabilise_logs(compile_cache.logs + logs, root_dir, tmp_dir, src_path)
        )
        return CompileContractResult(context, awst, log_txt, teal, output_files)
