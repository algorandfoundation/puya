import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_TYPED_ABI_CALL_TXN = TEST_CASES_DIR / "typed_abi_call_txn"


def test_abi_call_with_txns(deployer: Deployer) -> None:
    caller_client = deployer.create(_TYPED_ABI_CALL_TXN / "caller.py").client
    callee_client = deployer.create(_TYPED_ABI_CALL_TXN / "txn_contract.py").client

    deployer.localnet.account.ensure_funded(
        account_to_fund=caller_client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(400_000),
    )

    inner_fee = au.AlgoAmount.from_micro_algo(3000)

    def call(method: str) -> None:
        caller_client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=[b"a", b"b", callee_client.app_id],
                static_fee=inner_fee,
            )
        )

    call("test_call_with_txn")
    call("test_call_with_acfg")
    call("test_call_with_infer")
    call("test_call_with_acfg_no_return")
