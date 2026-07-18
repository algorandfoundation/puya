import random

import algokit_utils as au
import pytest
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

# A group that is expected to fail must skip algokit's simulate-based resource
# population, otherwise the rejection surfaces as a generic ValueError from the
# pre-flight simulate rather than from the actual send.
_NO_POPULATE = au.SendParams(populate_app_call_resources=False)
_REJECTED = (au.LogicError, TransactionComposerError)

_GROUP_TRANSACTIONS = EXAMPLES_DIR / "devportal" / "group_transactions"


def _deploy(deployer: Deployer) -> au.AppClient:
    """Deploy GroupTransactions and fund the app account so payments sent to
    it during a test group keep the app above its minimum balance."""
    client = deployer.create(_GROUP_TRANSACTIONS).client
    deployer.localnet.send.payment(
        au.PaymentParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(200_000),
        )
    )
    return client


def test_expect_payment_validates_preceding_payment(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    # [Payment -> AppCall]: expect_payment reads the txn at group_index - 1
    result = (
        localnet.new_group()
        .add_payment(
            au.PaymentParams(
                sender=account.addr,
                receiver=client.app_address,
                amount=au.AlgoAmount.from_micro_algo(12345),
            )
        )
        .add_app_call_method_call(
            client.params.call(au.AppClientMethodCallParams(method="expect_payment", args=[12345]))
        )
        .send()
    )
    assert result.returns[-1].value == 12345


def test_expect_payment_wrong_amount_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    with pytest.raises(_REJECTED):
        (
            localnet.new_group()
            .add_payment(
                au.PaymentParams(
                    sender=account.addr,
                    receiver=client.app_address,
                    amount=au.AlgoAmount.from_micro_algo(1000),
                )
            )
            .add_app_call_method_call(
                client.params.call(
                    au.AppClientMethodCallParams(method="expect_payment", args=[9999])
                )
            )
            .send(_NO_POPULATE)
        )


def test_expect_payment_missing_preceding_txn_is_rejected(deployer: Deployer) -> None:
    client = _deploy(deployer)

    with pytest.raises(au.LogicError):
        client.send.call(au.AppClientMethodCallParams(method="expect_payment", args=[1]))


def test_receive_funding_typed_args(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    asset = _create_asset(localnet, account)
    client = _deploy_for_asset(deployer, localnet, asset)

    # two transaction args bind positionally: the group is [pay, axfer, call],
    # exactly the parameter declaration order, ending at the app call
    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(54321),
    )
    axfer = au.AssetTransferParams(
        sender=account.addr,
        receiver=client.app_address,
        asset_id=asset,
        amount=1000,
    )
    result = client.send.call(
        au.AppClientMethodCallParams(method="receive_funding", args=[pay, axfer, asset, 54321])
    )
    assert result.abi_return == 54321 + 1000


def test_receive_funding_wrong_amount_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    asset = _create_asset(localnet, account)
    client = _deploy_for_asset(deployer, localnet, asset)

    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(100),
    )
    axfer = au.AssetTransferParams(
        sender=account.addr,
        receiver=client.app_address,
        asset_id=asset,
        amount=1000,
    )
    with pytest.raises(au.LogicError, match="wrong payment amount"):
        client.send.call(
            au.AppClientMethodCallParams(method="receive_funding", args=[pay, axfer, asset, 200])
        )


def test_receive_funding_swapped_txn_order_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    asset = _create_asset(localnet, account)
    client = _deploy_for_asset(deployer, localnet, asset)

    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(100),
    )
    axfer = au.AssetTransferParams(
        sender=account.addr,
        receiver=client.app_address,
        asset_id=asset,
        amount=1000,
    )
    # supplying the transactions in the wrong order puts a Payment where the
    # router asserts an AssetTransfer (and vice versa); the failure may
    # surface client-side (arg type validation) or on-chain (type assert)
    with pytest.raises((au.LogicError, ValueError, TransactionComposerError)):
        client.send.call(
            au.AppClientMethodCallParams(method="receive_funding", args=[axfer, pay, asset, 100])
        )


def test_chained_app_call_decodes_previous_log(
    deployer: Deployer, localnet: au.AlgorandClient
) -> None:
    chained = _deploy(deployer)
    observer = _deploy(deployer)

    pay = au.PaymentParams(
        sender=deployer.account.addr,
        receiver=chained.app_address,
        amount=au.AlgoAmount.from_micro_algo(777),
    )
    # group: [payment, expect_payment call, chained_app_call call]
    result = (
        localnet.new_group()
        .add_payment(pay)
        .add_app_call_method_call(
            chained.params.call(au.AppClientMethodCallParams(method="expect_payment", args=[777]))
        )
        .add_app_call_method_call(
            observer.params.call(au.AppClientMethodCallParams(method="chained_app_call", args=[]))
        )
        .send()
    )
    assert result.returns[-1].value == 777


def test_observe_app_call_typed_arg(deployer: Deployer, localnet: au.AlgorandClient) -> None:
    chained = _deploy(deployer)
    observer = _deploy(deployer)

    pay = au.PaymentParams(
        sender=deployer.account.addr,
        receiver=chained.app_address,
        amount=au.AlgoAmount.from_micro_algo(321),
    )
    prior = chained.params.call(au.AppClientMethodCallParams(method="expect_payment", args=[321]))
    # `prior` is supplied as the typed txn arg, so algokit places it
    # immediately before the observe call; its own preceding payment is
    # added to the group explicitly, giving [payment, prior, observe]
    result = (
        localnet.new_group()
        .add_payment(pay)
        .add_app_call_method_call(
            observer.params.call(
                au.AppClientMethodCallParams(method="observe_app_call", args=[prior])
            )
        )
        .send()
    )
    assert result.returns[-1].value == 321


def test_strict_position_accepts_fixed_shape(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    asset_id = localnet.send.asset_create(
        au.AssetCreateParams(
            sender=account.addr,
            total=1_000,
            decimals=0,
            default_frozen=False,
            asset_name="strict",
            unit_name="STR",
        )
    ).asset_id

    # [Payment(0), AppCall(1), AssetTransfer(2)]; pay.sender == axfer.asset_receiver
    result = (
        localnet.new_group()
        .add_payment(
            au.PaymentParams(
                sender=account.addr,
                receiver=client.app_address,
                amount=au.AlgoAmount.from_micro_algo(0),
            )
        )
        .add_app_call_method_call(
            client.params.call(au.AppClientMethodCallParams(method="strict_position", args=[3]))
        )
        .add_asset_transfer(
            au.AssetTransferParams(
                sender=account.addr,
                receiver=account.addr,
                asset_id=asset_id,
                amount=0,
            )
        )
        .send()
    )
    assert result.returns[-1].value is None


def test_strict_position_wrong_size_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    with pytest.raises(_REJECTED, match="wrong group size"):
        (
            localnet.new_group()
            .add_payment(
                au.PaymentParams(
                    sender=account.addr,
                    receiver=client.app_address,
                    amount=au.AlgoAmount.from_micro_algo(0),
                )
            )
            .add_app_call_method_call(
                client.params.call(
                    au.AppClientMethodCallParams(method="strict_position", args=[3])
                )
            )
            .send(_NO_POPULATE)
        )


def test_strict_position_wrong_index_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    asset_id = localnet.send.asset_create(
        au.AssetCreateParams(
            sender=account.addr,
            total=1_000,
            decimals=0,
            default_frozen=False,
            asset_name="strict2",
            unit_name="ST2",
        )
    ).asset_id

    with pytest.raises(_REJECTED, match="must be index 1"):
        (
            localnet.new_group()
            .add_app_call_method_call(
                client.params.call(
                    au.AppClientMethodCallParams(method="strict_position", args=[3])
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=account.addr,
                    receiver=client.app_address,
                    amount=au.AlgoAmount.from_micro_algo(0),
                )
            )
            .add_asset_transfer(
                au.AssetTransferParams(
                    sender=account.addr,
                    receiver=account.addr,
                    asset_id=asset_id,
                    amount=0,
                )
            )
            .send(_NO_POPULATE)
        )


def test_expect_asset_transfer_missing_preceding_txn_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)

    asset_id = localnet.send.asset_create(
        au.AssetCreateParams(
            sender=account.addr,
            total=1_000,
            decimals=0,
            default_frozen=False,
            asset_name="axfer",
            unit_name="AXF",
        )
    ).asset_id

    with pytest.raises(au.LogicError):
        client.send.call(
            au.AppClientMethodCallParams(method="expect_asset_transfer", args=[asset_id])
        )


def test_expect_asset_transfer_wrong_txn_type_is_rejected(
    deployer: Deployer,
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
    asset_a: int,
) -> None:
    client = _deploy(deployer)

    # a Payment precedes the call where an AssetTransfer is expected, so the
    # gtxn.AssetTransferTransaction(...) typed lookup itself fails
    with pytest.raises(_REJECTED):
        (
            localnet.new_group()
            .add_payment(
                au.PaymentParams(
                    sender=account.addr,
                    receiver=client.app_address,
                    amount=au.AlgoAmount.from_micro_algo(1000),
                )
            )
            .add_app_call_method_call(
                client.params.call(
                    au.AppClientMethodCallParams(
                        method="expect_asset_transfer",
                        args=[asset_a],
                        asset_references=[asset_a],
                    )
                )
            )
            .send(_NO_POPULATE)
        )


def _create_asset(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> int:
    """A fresh asset for tests that transfer units away: the shared session
    `asset_a` fixture must stay untouched — other tests (e.g. test_amm) assert
    the session account still holds its full supply."""
    return localnet.send.asset_create(
        au.AssetCreateParams(sender=account.addr, total=10_000_000, note=random.randbytes(8))
    ).asset_id


def _deploy_for_asset(
    deployer: Deployer, localnet: au.AlgorandClient, asset_id: int
) -> au.AppClient:
    """Deploy GroupTransactions, fund the app account so it can hold an asset,
    and opt the app account into `asset_id` via the contract's inner transfer."""
    client = deployer.create(_GROUP_TRANSACTIONS).client
    localnet.send.payment(
        au.PaymentParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_algo(1),
        )
    )
    # opt_in_to_asset issues an inner zero-amount AssetTransfer; the static fee
    # must cover both the outer app call and that inner txn.
    client.send.call(
        au.AppClientMethodCallParams(
            method="opt_in_to_asset",
            args=[asset_id],
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    return client


def test_expect_asset_transfer_validates_preceding_transfer(
    deployer: Deployer,
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
) -> None:
    asset = _create_asset(localnet, account)
    client = _deploy_for_asset(deployer, localnet, asset)

    # [AssetTransfer -> AppCall]: expect_asset_transfer reads group_index - 1
    result = (
        localnet.new_group()
        .add_asset_transfer(
            au.AssetTransferParams(
                sender=account.addr,
                receiver=client.app_address,
                asset_id=asset,
                amount=750,
            )
        )
        .add_app_call_method_call(
            client.params.call(
                au.AppClientMethodCallParams(method="expect_asset_transfer", args=[asset])
            )
        )
        .send()
    )
    assert result.returns[-1].value == 750
