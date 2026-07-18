import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_INNER_TRANSACTIONS = EXAMPLES_DIR / "devportal" / "inner_transactions"


def _deploy_funded(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> au.AppClient:
    """Deploy InnerTransactions and fund its app account so it can issue
    inner transactions and meet minimum balance for created assets/apps."""
    client = deployer.create((_INNER_TRANSACTIONS / "contract.py", "InnerTransactions")).client
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_algo(2),
        )
    )
    return client


def test_payment(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    # one inner payment txn of 5000 microAlgo; outer fee covers inner fee=0
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="payment",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    assert result.abi_return == 5000


def test_fungible_asset_create(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="fungible_asset_create",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    asset_id = result.abi_return
    assert isinstance(asset_id, int)
    assert asset_id > 0

    info = localnet.asset.get_by_id(asset_id)
    assert info.total == 100_000_000_000
    assert info.decimals == 2
    assert info.unit_name == "RP"
    assert info.asset_name == "Royalty Points"


def test_non_fungible_asset_create(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="non_fungible_asset_create",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    asset_id = result.abi_return
    assert isinstance(asset_id, int)
    assert asset_id > 0

    info = localnet.asset.get_by_id(asset_id)
    assert info.total == 100
    assert info.asset_name == "Mona Lisa"
    assert info.unit_name == "ML"


def test_asset_lifecycle(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    def call(method: str, args: list[object], fee: int = 2000) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args,
                static_fee=au.AlgoAmount.from_micro_algo(fee),
            )
        ).abi_return

    # create an asset the app fully controls (manager/reserve/freeze/clawback)
    asset_id = call("non_fungible_asset_create", [])
    assert isinstance(asset_id, int)

    # opt the app account into its own asset
    call("asset_opt_in", [asset_id])

    # freeze the app account's holding while the app still holds freeze authority
    call("asset_freeze", [client.app_address, asset_id])
    holding = localnet.asset.get_account_information(client.app_address, asset_id)
    assert holding.frozen is True

    # reconfigure: the app keeps manager/reserve, hands freeze/clawback to caller
    call("asset_config", [asset_id])
    info = localnet.asset.get_by_id(asset_id)
    assert info.manager == client.app_address

    # delete the asset (only possible while the manager holds the full supply)
    call("asset_delete", [asset_id])

    # the asset no longer exists
    with pytest.raises(Exception):  # noqa: B017, PT011
        localnet.asset.get_by_id(asset_id)


def test_asset_config_of_immutable_asset_is_rejected(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    # fungible_asset_create leaves manager/reserve/freeze/clawback unset,
    # making the asset immutable
    asset_id = client.send.call(
        au.AppClientMethodCallParams(
            method="fungible_asset_create",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    ).abi_return
    assert isinstance(asset_id, int)

    # the inner AssetConfig fails because there is no manager to authorize it
    with pytest.raises(au.LogicError):
        client.send.call(
            au.AppClientMethodCallParams(
                method="asset_config",
                args=[asset_id],
                static_fee=au.AlgoAmount.from_micro_algo(2000),
            )
        )


def test_asset_transfer_and_revoke(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    def call(method: str, args: list[object]) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args,
                static_fee=au.AlgoAmount.from_micro_algo(2000),
            )
        ).abi_return

    # non_fungible_asset_create sets clawback to the app, so the app can revoke;
    # the app holds the full supply (total=100) and is the creator (auto opted-in).
    asset_id = call("non_fungible_asset_create", [])
    assert isinstance(asset_id, int)

    # a fresh account opts in so it can receive a transfer
    receiver = localnet.account.random()
    localnet.account.ensure_funded(
        account_to_fund=receiver.addr,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_algo(1),
    )
    localnet.send.asset_opt_in(
        au.AssetOptInParams(sender=receiver.addr, asset_id=asset_id, signer=receiver.signer)
    )

    # app transfers 50 units to the receiver
    call("asset_transfer", [asset_id, receiver.addr, 50])
    holding = localnet.asset.get_account_information(receiver.addr, asset_id)
    assert holding.balance == 50

    # app revokes (claws back) 20 units from the receiver
    call("asset_revoke", [asset_id, receiver.addr, 20])
    holding = localnet.asset.get_account_information(receiver.addr, asset_id)
    assert holding.balance == 30


def test_multi_inner_txns(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    # deploy a HelloWorldContract target via the contract's own deploy method
    target_id = client.send.call(
        au.AppClientMethodCallParams(
            method="arc4_deploy_app",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    ).abi_return
    assert isinstance(target_id, int)

    # multi_inner_txns issues a grouped Payment + ApplicationCall (2 inner txns)
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="multi_inner_txns",
            args=[target_id],
            static_fee=au.AlgoAmount.from_micro_algo(3000),
            app_references=[target_id],
        )
    )
    multi_result = result.abi_return
    assert isinstance(multi_result, list | tuple)
    pay_amount, hello = multi_result
    assert pay_amount == 5000
    assert hello == "Hello, World"


def test_deploy_app(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="deploy_app",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    app_id = result.abi_return
    assert isinstance(app_id, int)
    assert app_id > 0


def test_arc4_deploy_app(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="arc4_deploy_app",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    app_id = result.abi_return
    assert isinstance(app_id, int)
    assert app_id > 0


def test_noop_app_call(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy_funded(deployer, localnet, account)

    # deploy a HelloWorldContract to call into
    target_id = client.send.call(
        au.AppClientMethodCallParams(
            method="deploy_app",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    ).abi_return
    assert isinstance(target_id, int)

    # noop_app_call issues two inner ApplicationCalls (manual + abi_call)
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="noop_app_call",
            args=[target_id],
            static_fee=au.AlgoAmount.from_micro_algo(3000),
            app_references=[target_id],
        )
    )
    noop_result = result.abi_return
    assert isinstance(noop_result, list | tuple)
    first, second = noop_result
    assert first == "Hello, World"
    assert second == "Hello, again"
