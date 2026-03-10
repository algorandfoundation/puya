import pytest
from algopy import Account, ImmutableArray, UInt64
from algopy_testing import AlgopyTestContext, algopy_testing_context
from contract import MultiTxnDistributor


def _make_contract_and_app_account(ctx: AlgopyTestContext) -> tuple[MultiTxnDistributor, Account]:
    contract = MultiTxnDistributor()
    return contract, ctx.ledger.get_app(contract).address


class TestDistributeFixed:
    def test_splits_payment_equally_to_3_receivers(self) -> None:
        with algopy_testing_context() as ctx:
            contract, app_account = _make_contract_and_app_account(ctx)
            r1, r2, r3 = ctx.any.account(), ctx.any.account(), ctx.any.account()

            pay = ctx.any.txn.payment(receiver=app_account, amount=900_000)
            result = contract.distribute_fixed(pay, r1, r2, r3)

            assert result == (UInt64(300_000), UInt64(300_000), UInt64(300_000))

    def test_asserts_funds_sent_to_app_address(self) -> None:
        with algopy_testing_context() as ctx:
            contract, _ = _make_contract_and_app_account(ctx)
            wrong_receiver = ctx.any.account()
            r1, r2, r3 = ctx.any.account(), ctx.any.account(), ctx.any.account()

            pay = ctx.any.txn.payment(receiver=wrong_receiver, amount=900_000)
            with pytest.raises(AssertionError, match="funds must be sent to app"):
                contract.distribute_fixed(pay, r1, r2, r3)


class TestDistributeDynamic:
    @pytest.mark.xfail(
        reason="ImmutableArray and itxn.Payment.stage() not fully implemented"
        " in algorand-python-testing",
        raises=(TypeError, AttributeError),
    )
    def test_distributes_to_variable_length_receiver_list(self) -> None:
        with algopy_testing_context() as ctx:
            contract, app_account = _make_contract_and_app_account(ctx)
            r1, r2 = ctx.any.account(), ctx.any.account()

            receivers = ImmutableArray(r1, r2)
            pay = ctx.any.txn.payment(receiver=app_account, amount=1000)
            share = contract.distribute_dynamic(pay, receivers)

            assert share == UInt64(500)

    def test_rejects_empty_receivers_array(self) -> None:
        with algopy_testing_context() as ctx:
            contract, app_account = _make_contract_and_app_account(ctx)

            receivers = ImmutableArray[Account]()
            pay = ctx.any.txn.payment(receiver=app_account, amount=1000)
            with pytest.raises(AssertionError, match="must have at least one receiver"):
                contract.distribute_dynamic(pay, receivers)
