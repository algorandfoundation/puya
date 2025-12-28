import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer

_INNER_TRANSACTIONS = TEST_CASES_DIR / "inner_transactions"


def test_inner_transactions(deployer_o: Deployer) -> None:
    client = deployer_o.create_bare(_INNER_TRANSACTIONS / "contract.py").client

    # Fund app to meet minimum balance requirements
    deployer_o.localnet.send.payment(
        au.PaymentParams(
            sender=deployer_o.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(9 * 100_000),
        )
    )

    # Increased fee to cover inner transactions (1 + 16)
    inner_fee = au.AlgoAmount.from_micro_algo(1000 * 17)

    client.send.bare.call(au.AppClientBareCallParams(args=[b"test1"], static_fee=inner_fee))

    client.send.bare.call(au.AppClientBareCallParams(args=[b"test2"], static_fee=inner_fee))

    client.send.bare.call(
        au.AppClientBareCallParams(args=[b"test2", b"do 2nd submit"], static_fee=inner_fee)
    )

    client.send.bare.call(au.AppClientBareCallParams(args=[b"test3"], static_fee=inner_fee))

    client.send.bare.call(au.AppClientBareCallParams(args=[b"test4"], static_fee=inner_fee))


def test_inner_transactions_loop(deployer_o: Deployer) -> None:
    # Increased fee to cover inner transactions (1 + 4)
    inner_fee = au.AlgoAmount.from_micro_algo(1000 * 5)

    result = deployer_o.create_bare(_INNER_TRANSACTIONS / "itxn_loop.py", static_fee=inner_fee)

    assert decode_logs(result.logs, "bibibibi") == [b"", 0, b"A", 1, b"AB", 2, b"ABC", 3]


def test_inner_transactions_c2c(deployer: Deployer) -> None:
    client = deployer.create(_INNER_TRANSACTIONS / "c2c.py").client
    account = deployer.account

    # Fund app for inner transactions
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )

    # Bootstrap - creates inner app
    bootstrap_result = client.send.call(
        au.AppClientMethodCallParams(
            method="bootstrap",
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    inner_app_id = bootstrap_result.abi_return
    assert isinstance(inner_app_id, int)

    # Call log_greetings with inner app reference
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="log_greetings",
            args=["There"],
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    assert result.confirmation.logs == [b"HelloWorld returned: Hello, There"]


def test_inner_transactions_array_access(deployer: Deployer) -> None:
    result = deployer.create(_INNER_TRANSACTIONS / "array_access.py")
    client = result.client
    account = deployer.account

    # Fund app for inner transactions
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    # Test both branches
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_branching_array_call",
            args=[True],
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_branching_array_call",
            args=[False],
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )


def test_inner_transactions_tuple(deployer: Deployer) -> None:
    result = deployer.create(_INNER_TRANSACTIONS / "field_tuple_assignment.py")
    client = result.client

    # Test tuple assignment methods (7 inner txns)
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_assign_tuple",
            static_fee=au.AlgoAmount.from_micro_algo(7000),
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_assign_tuple_mixed",
            static_fee=au.AlgoAmount.from_micro_algo(7000),
        )
    )


def test_inner_transactions_asset_transfer(deployer: Deployer) -> None:
    result = deployer.create(_INNER_TRANSACTIONS / "asset_transfer.py")
    client = result.client
    account = deployer.account

    # Fund app for inner transactions
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    # Call create_and_transfer (3 inner txns)
    client.send.call(
        au.AppClientMethodCallParams(
            method="create_and_transfer",
            static_fee=au.AlgoAmount.from_micro_algo(3000),
        )
    )


def test_inner_transactions_assignment(deployer: Deployer) -> None:
    result = deployer.create(TEST_CASES_DIR / "inner_transactions_assignment")
    client = result.client
    account = deployer.account

    # Fund app for inner transactions
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(400_000),
    )

    # Test itxn slice (8 inner txns)
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_itxn_slice",
            static_fee=au.AlgoAmount.from_micro_algo(8000),
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_itxn_nested",
            static_fee=au.AlgoAmount.from_micro_algo(8000),
        )
    )
