import functools
import os
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
from puya.compile import awst_to_teal, parse_with_mypy
from puya.context import CompileContext
from puya.errors import Errors
from puya.logging_config import LogLevel, configure_logging
from puya.options import PuyaOptions
from puya.parse import get_parse_sources

VCS_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = VCS_ROOT / "examples"
TEST_CASES_DIR = VCS_ROOT / "test_cases"


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
def get_awst_cache(*root_dirs: Path) -> CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with structlog.testing.capture_logs() as logs:
        context = parse_with_mypy(PuyaOptions(paths=root_dirs))
        awst = transform_ast(context)
        return CompileCache(context, awst, logs)


@functools.cache
def parse_src_to_awst(
    src_path: Path,
) -> CompileCache:
    root_dir = _get_root_dir(src_path)
    if root_dir:
        orig_dir = os.curdir
        os.chdir(root_dir)
        try:
            compile_cache = get_awst_cache(root_dir)
        finally:
            os.chdir(orig_dir)
    else:
        compile_cache = get_awst_cache(src_path)

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


@functools.cache
def compile_src(src_path: Path, optimization_level: int, debug_level: int) -> CompiledContract:
    compile_cache = parse_src_to_awst(src_path)
    context = compile_cache.context
    awst = compile_cache.module_awst
    context = attrs.evolve(
        context,
        options=attrs.evolve(
            context.options,
            optimization_level=optimization_level,
            debug_level=debug_level,
        ),
    )
    teal = awst_to_teal(context, awst)
    assert teal is not None, "compile error"
    ((contract,),) = teal.values()
    return contract
