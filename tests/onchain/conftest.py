from pathlib import Path

import algokit_utils as au
import pytest

from tests.utils.deployer import Deployer

_ONCHAIN_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    _ = config
    mark = pytest.mark.localnet
    for item in items:
        if _ONCHAIN_DIR in item.path.parents:
            item.add_marker(mark)


@pytest.fixture(params=[0, 1, 2])
def optimization_level(request: pytest.FixtureRequest) -> int:
    return int(request.param)


@pytest.fixture
def deployer_o(
    localnet: au.AlgorandClient, account: au.AddressWithSigners, optimization_level: int
) -> Deployer:
    """Deployer fixture parameterized by optimization_level (0, 1, 2)."""
    return Deployer(localnet=localnet, account=account, optimization_level=optimization_level)
