import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_arc4_routing(deployer: Deployer) -> None:
    app_client = deployer.create_bare(TEST_CASES_DIR / "abi_routing" / "contract.py").client

    # opt_in
    response = app_client.send.opt_in(
        au.AppClientMethodCallParams(
            method="opt_in",
            args=[42, b"43"],
        )
    )
    assert response.confirmation.confirmed_round

    # method_with_default_args
    app_client.send.call(
        au.AppClientMethodCallParams(
            method="method_with_default_args",
            args=[],
        )
    )

    # hello_with_algopy_string
    hello_result = app_client.send.call(
        au.AppClientMethodCallParams(
            method="hello_with_algopy_string",
            args=["Algopy"],
        )
    )
    assert hello_result.abi_return == "Hello Algopy!"


def test_arc4_routing_with_many_params(
    localnet: au.AlgorandClient,
    deployer: Deployer,
    account: au.AddressWithSigners,
    asset_a: int,
    asset_b: int,
) -> None:
    app_client = deployer.create_bare(TEST_CASES_DIR / "abi_routing" / "contract.py").client

    pay_txn = localnet.create_transaction.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client.app_address,
            amount=au.AlgoAmount.from_micro_algo(100_000),
            note=b"Test 1",
        )
    )
    pay_txn2 = localnet.create_transaction.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client.app_address,
            amount=au.AlgoAmount.from_micro_algo(200_000),
            note=b"Test 2",
        )
    )

    result = app_client.send.call(
        au.AppClientMethodCallParams(
            method="method_with_more_than_15_args",
            args=[
                1,  # a
                1,  # b
                1,  # c
                1,  # d
                asset_a,  # asset
                1,  # e
                1,  # f
                pay_txn,  # pay
                1,  # g
                1,  # h
                1,  # i
                1,  # j
                1,  # k
                1,  # l
                1,  # m
                1,  # n
                1,  # o
                1,  # p
                1,  # q
                1,  # r
                b"a",  # s
                b"b",  # t
                asset_b,  # asset2
                pay_txn2,  # pay2
                1,  # u
                1,  # v
            ],
        )
    )
    assert result.abi_return == 20

    assert result.confirmation.logs is not None
    logged_string = result.confirmation.logs[0]
    assert logged_string == b"ab"

    result2 = app_client.send.call(
        au.AppClientMethodCallParams(
            method="method_with_15_args",
            args=[
                1,  # one
                1,  # two
                1,  # three
                1,  # four
                1,  # five
                1,  # six
                1,  # seven
                1,  # eight
                1,  # nine
                1,  # ten
                1,  # eleven
                1,  # twelve
                1,  # thirteen
                1,  # fourteen
                b"fifteen",  # fifteen
            ],
        )
    )
    assert result2.abi_return == b"fifteen"
