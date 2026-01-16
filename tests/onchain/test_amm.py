import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_DEFAULT_FEE = au.AlgoAmount.from_micro_algo(1_000)


def test_amm(
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
    deployer: Deployer,
    asset_a: int,
    asset_b: int,
) -> None:
    app_client = deployer.create(EXAMPLES_DIR / "amm").client

    pay_txn = localnet.create_transaction.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client.app_address,
            amount=au.AlgoAmount.from_algo(10),
        )
    )

    def abi_call[T](method: str, args: list[object], typ: type[T] | None = None) -> T:
        response = app_client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args,
                sender=account.addr,
                max_fee=_DEFAULT_FEE * 100,
            ),
            send_params=au.SendParams(cover_app_call_inner_transaction_fees=True),
        )
        if typ:
            assert isinstance(response.abi_return, typ), f"expected return of type {typ}"
            return response.abi_return
        else:
            return None  # type: ignore[return-value]

    pool_token = abi_call("bootstrap", [pay_txn, asset_a, asset_b], typ=int)

    def get_token_balances(addr: str) -> dict[int, int]:
        account_info = localnet.client.algod.account_information(addr)

        return {
            h.asset_id: h.amount
            for h in account_info.assets or ()
            if h.asset_id in (pool_token, asset_a, asset_b)
        }

    def get_ratio() -> int:
        state = app_client.get_global_state()
        ratio = state["ratio"].value
        assert isinstance(ratio, int)
        return ratio

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 10_000_000, asset_b: 10_000_000}
    assert app_balance == {asset_a: 0, asset_b: 0, pool_token: 10_000_000_000}
    assert get_ratio() == 0
    # pool_id should be newer than asset a + b
    assert pool_token > asset_a
    assert pool_token > asset_b

    # opt user into tokens
    # fund user account with assets a & b
    (
        localnet.new_group()
        .add_asset_opt_in(au.AssetOptInParams(asset_id=asset_a, sender=account.addr))
        .add_asset_opt_in(au.AssetOptInParams(asset_id=asset_b, sender=account.addr))
        .add_asset_opt_in(au.AssetOptInParams(asset_id=pool_token, sender=account.addr))
        .send()
    )

    # mint
    a_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=10_000, asset_id=asset_a
        )
    )
    b_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=3_000, asset_id=asset_b
        )
    )

    # mint
    abi_call("mint", [a_xfer, b_xfer])

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 9_990_000, asset_b: 9_997_000, pool_token: 4_477}
    assert app_balance == {asset_a: 10_000, asset_b: 3_000, pool_token: 9_999_995_523}
    assert get_ratio() == 3_333

    # mint again
    a_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=100_000, asset_id=asset_a
        )
    )
    b_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=1_000, asset_id=asset_b
        )
    )
    abi_call("mint", [a_xfer, b_xfer])

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 9_890_000, asset_b: 9_996_000, pool_token: 5_967}
    assert app_balance == {asset_a: 110_000, asset_b: 4_000, pool_token: 9_999_994_033}
    assert get_ratio() == 27_500

    # swap asset_a for asset_b
    swap_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=500, asset_id=asset_a
        )
    )
    abi_call("swap", [swap_xfer])

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 9_903_252, asset_b: 9_996_000, pool_token: 5_967}
    assert app_balance == {asset_a: 96_748, asset_b: 4_000, pool_token: 9_999_994_033}
    assert get_ratio() == 24_187

    # swap asset_b for asset_a
    swap_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=500, asset_id=asset_b
        )
    )
    abi_call("swap", [swap_xfer])

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 9_903_252, asset_b: 9_995_523, pool_token: 5_967}
    assert app_balance == {asset_a: 96_748, asset_b: 4_477, pool_token: 9_999_994_033}
    assert get_ratio() == 21_610

    # burn
    pool_xfer = localnet.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=account.addr, receiver=app_client.app_address, amount=100, asset_id=pool_token
        )
    )
    abi_call("burn", [pool_xfer])

    account_balance = get_token_balances(account.addr)
    app_balance = get_token_balances(app_client.app_address)
    assert account_balance == {asset_a: 9_904_929, asset_b: 9_995_600, pool_token: 5_867}
    assert app_balance == {asset_a: 95_071, asset_b: 4_400, pool_token: 9_999_994_133}
    assert get_ratio() == 21_607
