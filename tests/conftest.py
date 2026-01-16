from collections.abc import Iterable
from random import randbytes

import algokit_utils as au
import pytest
from _pytest.mark import ParameterSet

from puya import log
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.utils import PuyaTestCase
from tests.utils.deployer import Deployer


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


@pytest.fixture
def deployer(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> Deployer:
    return Deployer(localnet=localnet, account=account)


@pytest.fixture(scope="session")
def algod_client() -> Iterable[au.AlgodClient]:
    config = au.ClientManager.get_default_localnet_config("algod")
    algod = au.ClientManager.get_algod_client(config)
    yield algod
    algod.close()


@pytest.fixture(scope="session")
def kmd_client() -> Iterable[au.KmdClient]:
    config = au.ClientManager.get_default_localnet_config("kmd")
    kmd = au.ClientManager.get_kmd_client(config)
    yield kmd
    kmd.close()


@pytest.fixture(scope="session")
def localnet_clients(algod_client: au.AlgodClient, kmd_client: au.KmdClient) -> au.AlgoSdkClients:
    return au.AlgoSdkClients(algod=algod_client, kmd=kmd_client)


@pytest.fixture(scope="session")
def account(localnet_clients: au.AlgoSdkClients) -> au.AddressWithSigners:
    # retrieving localnet dispenser is slow so cache for session
    # reuse localnet_clients to avoid creating unclosed connections
    return au.AlgorandClient(localnet_clients).account.localnet_dispenser()


@pytest.fixture
def localnet(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AlgorandClient:
    # algorand client is stateful, so create a new instance each test
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    return localnet


@pytest.fixture(scope="session")
def asset_a(localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners) -> int:
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    return _create_asset(localnet, account, "a")


@pytest.fixture(scope="session")
def asset_b(localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners) -> int:
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    return _create_asset(localnet, account, "b")


def _create_asset(
    localnet: au.AlgorandClient, account: au.AddressWithSigners, asset_unit: str
) -> int:
    result = localnet.send.asset_create(
        au.AssetCreateParams(
            sender=account.addr,
            total=10_000_000,
            decimals=0,
            default_frozen=False,
            asset_name=f"asset {asset_unit}",
            unit_name=asset_unit,
            note=randbytes(8),
        )
    )
    return result.asset_id
