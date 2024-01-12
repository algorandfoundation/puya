import pytest
from algokit_utils import (
    Account,
    get_algod_client,
    get_default_localnet_config,
    get_localnet_default_account,
)
from algosdk import transaction
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, TransactionWithSigner
from algosdk.v2client.algod import AlgodClient
from puya.logging_config import LogLevel, configure_logging


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
