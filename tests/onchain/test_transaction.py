import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_transaction(
    localnet: au.AlgorandClient,
    deployer: Deployer,
    account: au.AddressWithSigners,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "transaction").client

    # ensure app meets minimum balance requirements
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client.app_address,
            amount=au.AlgoAmount.from_micro_algo(100_000),
        )
    )

    # call pay method with a payment transaction
    pay_txn = localnet.create_transaction.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client.app_address,
            amount=au.AlgoAmount.from_micro_algo(1001),
        )
    )
    app_client.send.call(
        au.AppClientMethodCallParams(
            method="pay",
            args=[pay_txn],
        )
    )

    # TODO: call remaining transaction methods
