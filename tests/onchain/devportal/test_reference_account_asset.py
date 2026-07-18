import random

import algokit_utils as au
import pytest
from algokit_common import public_key_from_address

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_REFERENCE_ACCOUNT_ASSET = EXAMPLES_DIR / "devportal" / "reference_account_asset"


def _deploy(deployer: Deployer, known_account: str, known_asset_id: int) -> au.AppClient:
    """Deploy ReferenceAccountAsset with both template variables filled."""
    spec = compile_arc56(_REFERENCE_ACCOUNT_ASSET)
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
            deploy_time_params={
                "TMPL_KNOWN_ACCOUNT": public_key_from_address(known_account),
                "TMPL_KNOWN_ASSET": known_asset_id,
            }
        ),
    )
    return client


def _create_asset(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> int:
    """A fresh asset for tests that transfer units away: the shared session
    `asset_a` fixture must stay untouched — other tests (e.g. test_amm) assert
    the session account still holds its full supply."""
    return localnet.send.asset_create(
        au.AssetCreateParams(sender=account.addr, total=10_000_000, note=random.randbytes(8))
    ).asset_id


def _funded_account(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> au.AddressWithSigners:
    """Create and fund a fresh account so it can opt into / hold assets."""
    acct = localnet.account.random()
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=acct.addr,
            amount=au.AlgoAmount.from_algo(1),
            note=random.randbytes(8),
        )
    )
    return acct


def test_known_pair_reads_holding(
    deployer: Deployer,
    account: au.AddressWithSigners,
    localnet: au.AlgorandClient,
) -> None:
    """The template-provided account/asset pair's holding is read by the no-arg variant."""
    holder = _funded_account(localnet, account)
    asset = _create_asset(localnet, account)
    # opt-in, then receive some units
    localnet.send.asset_transfer(
        au.AssetTransferParams(sender=holder.addr, receiver=holder.addr, asset_id=asset, amount=0)
    )
    transfer_amount = 777
    localnet.send.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr,
            receiver=holder.addr,
            asset_id=asset,
            amount=transfer_amount,
            note=random.randbytes(8),
        )
    )
    client = _deploy(deployer, holder.addr, asset)

    result = client.send.call(au.AppClientMethodCallParams(method="get_asset_balance"))
    assert result.abi_return == transfer_amount


def test_known_pair_account_not_opted_in(
    deployer: Deployer,
    account: au.AddressWithSigners,
    localnet: au.AlgorandClient,
    asset_a: int,
) -> None:
    """A template-provided account that never opted in trips the opt-in assertion."""
    holder = _funded_account(localnet, account)
    client = _deploy(deployer, holder.addr, asset_a)

    with pytest.raises(au.LogicError, match="Account is not opted in to the asset"):
        client.send.call(au.AppClientMethodCallParams(method="get_asset_balance"))


def test_with_arg_reads_opted_in_account_holding(
    deployer: Deployer,
    account: au.AddressWithSigners,
    localnet: au.AlgorandClient,
    asset_a: int,
) -> None:
    """After opting in and receiving a transfer, the holding is read correctly."""
    client = _deploy(deployer, account.addr, asset_a)

    holder = _funded_account(localnet, account)
    asset = _create_asset(localnet, account)

    # opt-in: 0-amount transfer from the account to itself
    localnet.send.asset_transfer(
        au.AssetTransferParams(
            sender=holder.addr,
            receiver=holder.addr,
            asset_id=asset,
            amount=0,
        )
    )

    # transfer some units from the asset creator to the holder
    transfer_amount = 1234
    localnet.send.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr,
            receiver=holder.addr,
            asset_id=asset,
            amount=transfer_amount,
            note=random.randbytes(8),
        )
    )

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="get_asset_balance_with_arg",
            args=[holder.addr, asset],
        )
    )
    assert result.abi_return == transfer_amount


def test_with_arg_opted_in_zero_balance(
    deployer: Deployer,
    account: au.AddressWithSigners,
    localnet: au.AlgorandClient,
    asset_a: int,
) -> None:
    """An opted-in account that received nothing has a zero holding."""
    client = _deploy(deployer, account.addr, asset_a)

    holder = _funded_account(localnet, account)
    localnet.send.asset_transfer(
        au.AssetTransferParams(
            sender=holder.addr,
            receiver=holder.addr,
            asset_id=asset_a,
            amount=0,
        )
    )

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="get_asset_balance_with_arg",
            args=[holder.addr, asset_a],
        )
    )
    assert result.abi_return == 0


def test_with_arg_not_opted_in_fails(
    deployer: Deployer,
    account: au.AddressWithSigners,
    localnet: au.AlgorandClient,
    asset_a: int,
) -> None:
    """An account that never opted into the asset trips the opt-in assertion."""
    client = _deploy(deployer, account.addr, asset_a)

    holder = _funded_account(localnet, account)
    with pytest.raises(au.LogicError, match="Account is not opted in to the asset"):
        client.send.call(
            au.AppClientMethodCallParams(
                method="get_asset_balance_with_arg",
                args=[holder.addr, asset_a],
            )
        )
