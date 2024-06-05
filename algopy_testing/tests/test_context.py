import algopy_testing
import algosdk
import pytest
from algopy import Bytes, UInt64
from algopy_testing.context import AlgopyTestContext, algopy_testing_context, get_test_context


def test_patch_global_fields() -> None:
    with algopy_testing_context() as context:
        context.patch_global_fields(min_txn_fee=UInt64(100), min_balance=UInt64(10))
        assert context.global_fields["min_txn_fee"] == 100
        assert context.global_fields["min_balance"] == 10

        with pytest.raises(AttributeError, match="InvalidField"):
            context.patch_global_fields(InvalidField=123)  # type: ignore   # noqa: PGH003


def test_patch_txn_fields() -> None:
    with algopy_testing_context() as context:
        dummy_account = algosdk.account.generate_account()[1]
        context.patch_txn_fields(sender=dummy_account, fee=UInt64(1000))
        assert context.txn_fields["sender"] == dummy_account
        assert context.txn_fields["fee"] == 1000

        with pytest.raises(AttributeError, match="InvalidField"):
            context.patch_txn_fields(InvalidField=123)  # type: ignore   # noqa: PGH003


def test_account_management() -> None:
    with algopy_testing_context() as context:
        address: str = algosdk.account.generate_account()[1]
        account = context.any_account(address=address, balance=UInt64(1000))
        assert context.get_account(str(account)).balance == 1000

        context.update_account(str(account), balance=UInt64(2000))
        assert context.get_account(str(account)).balance == 2000

        with pytest.raises(ValueError, match="Account not found"):
            context.update_account("invalid_address", balance=UInt64(2000))


def test_asset_management() -> None:
    with algopy_testing_context() as context:
        asset = context.any_asset(name=Bytes(b"TestAsset"), total=UInt64(1000))
        assert context.get_asset(int(asset.id)).name == b"TestAsset"

        context.update_asset(int(asset.id), name=Bytes(b"UpdatedAsset"))
        assert context.get_asset(int(asset.id)).name == b"UpdatedAsset"

        with pytest.raises(ValueError, match="Asset not found"):
            context.update_asset(9999, name=Bytes(b"NonExistentAsset"))


def test_application_management() -> None:
    with algopy_testing_context() as context:
        app = context.any_application(
            approval_program=Bytes(b"TestApp"),
            clear_state_program=Bytes(b"TestClear"),
        )

        application = context.get_application(app.id)

        assert application.approval_program == b"TestApp"
        assert application.clear_state_program == b"TestClear"


def test_transaction_group_management() -> None:
    with algopy_testing_context() as context:
        txn1 = context.any_pay_txn(sender="sender1", receiver="receiver1", amount=1000)
        txn2 = context.any_pay_txn(sender="sender2", receiver="receiver2", amount=2000)
        context.set_transaction_group([txn1, txn2])
        assert len(context.get_transaction_group()) == 2

        context.clear_transaction_group()
        assert len(context.get_transaction_group()) == 0


def test_inner_transaction_management() -> None:
    with algopy_testing_context() as context:
        itxn = algopy_testing.itxn.Payment(sender=context.any_account())
        context.add_inner_transaction(itxn)
        assert len(context.inner_transactions) == 1

        context.clear_inner_transactions()
        assert len(context.inner_transactions) == 0


def test_last_itxn_access() -> None:
    with algopy_testing_context() as context:
        from algopy.op import ITxn

        dummy_account = context.any_account()
        itxn = algopy_testing.itxn.Payment(sender=dummy_account)
        context.add_inner_transaction(itxn)
        assert len(context.inner_transactions) == 1
        assert ITxn.sender() == dummy_account


def test_context_clearing() -> None:
    with algopy_testing_context() as context:
        context.any_account(balance=UInt64(1000))
        context.any_asset(name=Bytes(b"TestAsset"), total=UInt64(1000))
        context.any_application(
            approval_program=Bytes(b"TestApp"),
            clear_state_program=Bytes(b"TestClear"),
        )
        context.clear()
        assert len(context.account_data) == 0
        assert len(context.asset_data) == 0
        assert len(context.application_data) == 0
        assert len(context.inner_transactions) == 0
        assert len(context.gtxns) == 0
        assert len(context.logs) == 0


def test_context_reset() -> None:
    with algopy_testing_context() as context:
        context.any_account(balance=UInt64(1000))
        context.any_asset(name=Bytes(b"TestAsset"), total=UInt64(1000))
        context.any_application(
            approval_program=Bytes(b"TestApp"),
            clear_state_program=Bytes(b"TestClear"),
        )
        context.reset()
        assert len(context.account_data) == 0
        assert len(context.asset_data) == 0
        assert len(context.application_data) == 0
        assert len(context.inner_transactions) == 0
        assert len(context.gtxns) == 0
        assert len(context.logs) == 0
        assert next(context._asset_id) == 1  # noqa: SLF001
        assert next(context._app_id) == 1  # noqa: SLF001


def test_algopy_testing_context() -> None:
    with algopy_testing_context() as context:
        assert isinstance(context, AlgopyTestContext)
        context.any_account(balance=UInt64(1000))
        assert len(context.account_data) == 1

    # When called outside of a context manager, it should raise an error
    with pytest.raises(LookupError):
        get_test_context()
