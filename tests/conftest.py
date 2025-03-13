from random import randbytes

import pytest
from _pytest.mark import ParameterSet
from algokit_utils import (
    Account,
    get_algod_client,
    get_default_localnet_config,
    get_localnet_default_account,
)
from algosdk import transaction
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner
from algosdk.v2client.algod import AlgodClient

from puya import log
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.utils import PuyaTestCase


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    # parametrize `test_case: PuyaTestCase` based on test cases in examples and test_cases dirs
    if "test_case" in metafunc.fixturenames:
        # only parametrize if not already parametrized
        mark = metafunc.definition.get_closest_marker("parametrize")
        if not mark or "test_case" not in mark.args[0]:
            params = [
                ParameterSet.param(
                    PuyaTestCase(item),
                    marks=[pytest.mark.slow] if item.name == "stress_tests" else [],
                )
                for root in (EXAMPLES_DIR, TEST_CASES_DIR)
                for item in root.iterdir()
                if item.is_dir() and not item.name.startswith((".", "_"))
            ]
            metafunc.parametrize("test_case", params, ids=lambda t: t.id)


@pytest.fixture(autouse=True, scope="session")
def _setup_logging() -> None:
    # configure logging for tests
    # note cache_logger should be False if calling configure_logging more than once
    log.configure_logging(
        min_log_level=log.LogLevel.info,
        cache_logger=False,
        reconfigure_stdio=False,
    )


@pytest.fixture(scope="session")
def algod_client() -> AlgodClient:
    return get_algod_client(get_default_localnet_config("algod"))


@pytest.fixture(scope="session")
def account(algod_client: AlgodClient) -> Account:
    return get_localnet_default_account(algod_client)


@pytest.fixture(scope="session")
def asset_a(algod_client: AlgodClient, account: Account) -> int:
    return _create_asset(algod_client, account, "a")


@pytest.fixture(scope="session")
def asset_b(algod_client: AlgodClient, account: Account) -> int:
    return _create_asset(algod_client, account, "b")


def _create_asset(algod_client: AlgodClient, account: Account, asset_unit: str) -> int:
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
                note=randbytes(8),
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
