import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_REFERENCE_ASSET = EXAMPLES_DIR / "devportal" / "reference_asset"

# the asset_a / asset_b fixtures create assets with this total supply
_ASSET_TOTAL = 10_000_000


def _deploy(deployer: Deployer, known_asset_id: int) -> au.AppClient:
    """Deploy ReferenceAsset with the TMPL_KNOWN_ASSET template variable filled."""
    spec = compile_arc56(_REFERENCE_ASSET)
    factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=deployer.localnet,
            app_spec=spec,
            default_sender=deployer.account.addr,
        )
    )
    client, _ = factory.send.bare.create(
        au.AppFactoryCreateParams(note=random.randbytes(8)),
        compilation_params=au.AppClientCompilationParams(
            deploy_time_params={"TMPL_KNOWN_ASSET": known_asset_id}
        ),
    )
    return client


def test_known_asset_total_supply(deployer: Deployer, asset_a: int) -> None:
    """The template-provided asset's total supply is read by the no-arg variant."""
    client = _deploy(deployer, asset_a)

    result = client.send.call(au.AppClientMethodCallParams(method="get_asset_total_supply"))
    assert result.abi_return == _ASSET_TOTAL


def test_known_asset_destroyed_fails(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    """A destroyed asset id no longer resolves, so reading `.total` fails."""
    created = localnet.send.asset_create(
        au.AssetCreateParams(
            sender=account.addr,
            total=1,
            manager=account.addr,  # required to be able to destroy the asset below
            note=random.randbytes(8),
        )
    )
    localnet.send.asset_destroy(
        au.AssetDestroyParams(sender=account.addr, asset_id=created.asset_id)
    )
    client = _deploy(deployer, created.asset_id)

    with pytest.raises(au.LogicError):
        client.send.call(au.AppClientMethodCallParams(method="get_asset_total_supply"))


def test_with_arg_returns_total_supply(deployer: Deployer, asset_a: int) -> None:
    """The with-argument variant reads the real total supply of a created asset."""
    client = _deploy(deployer, asset_a)

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="get_asset_total_supply_with_arg",
            args=[asset_a],
        )
    )
    assert result.abi_return == _ASSET_TOTAL


def test_with_arg_works_for_multiple_assets(
    deployer: Deployer, asset_a: int, asset_b: int
) -> None:
    """Each distinct asset reference returns its own total supply."""
    client = _deploy(deployer, asset_a)

    for asset_id in (asset_a, asset_b):
        result = client.send.call(
            au.AppClientMethodCallParams(
                method="get_asset_total_supply_with_arg",
                args=[asset_id],
                note=random.randbytes(8),
            )
        )
        assert result.abi_return == _ASSET_TOTAL
