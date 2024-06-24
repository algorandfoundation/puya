import algosdk
import pytest
from algopy import Bytes, TransactionType, UInt64
from algopy_testing import arc4
from algopy_testing.context import AlgopyTestContext, algopy_testing_context, get_test_context
from algopy_testing.itxn import PaymentInnerTransaction

from tests.artifacts.Arc4InnerTxns.contract import Arc4InnerTxnsContract
from tests.artifacts.GlobalStateValidator.contract import GlobalStateValidator


def test_patch_global_fields() -> None:
    with algopy_testing_context() as context:
        context.patch_global_fields(min_txn_fee=UInt64(100), min_balance=UInt64(10))
        assert context._global_fields["min_txn_fee"] == 100
        assert context._global_fields["min_balance"] == 10

        with pytest.raises(AttributeError, match="InvalidField"):
            context.patch_global_fields(InvalidField=123)  # type: ignore   # noqa: PGH003


def test_patch_txn_fields() -> None:
    with algopy_testing_context() as context:
        dummy_account = algosdk.account.generate_account()[1]
        context.patch_txn_fields(sender=dummy_account, fee=UInt64(1000))
        assert context._txn_fields["sender"] == dummy_account
        assert context._txn_fields["fee"] == 1000

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
        txn1 = context.any_payment_transaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(1000),
        )
        txn2 = context.any_payment_transaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(2000),
        )
        context.set_transaction_group([txn1, txn2])
        assert len(context.get_transaction_group()) == 2

        context.clear_transaction_group()
        assert len(context.get_transaction_group()) == 0


def test_last_itxn_access() -> None:
    with algopy_testing_context() as context:
        contract = Arc4InnerTxnsContract()
        dummy_asset = context.any_asset()
        contract.opt_in_dummy_asset(dummy_asset)
        assert len(context.get_submitted_itxn_group(0)) == 1
        itxn = context.last_submitted_itxn.asset_transfer
        assert itxn.asset_sender == context.default_application.address
        assert itxn.asset_receiver == context.default_application.address
        assert itxn.amount == UInt64(0)
        assert itxn.type == TransactionType.AssetTransfer


def test_context_clearing() -> None:
    with algopy_testing_context() as context:
        context.any_account(balance=UInt64(1000))
        context.any_asset(name=Bytes(b"TestAsset"), total=UInt64(1000))
        context.any_application(
            approval_program=Bytes(b"TestApp"),
            clear_state_program=Bytes(b"TestClear"),
        )
        context.clear()
        assert len(context._account_data) == 0
        assert len(context._asset_data) == 0
        assert len(context._application_data) == 0
        with pytest.raises(ValueError, match="No inner transaction groups submitted yet!"):
            context.get_submitted_itxn_group(0)
        assert len(context.get_transaction_group()) == 0
        assert len(context._application_logs) == 0
        assert len(context._contracts) == 0
        assert len(context._scratch_spaces) == 0
        assert context._active_transaction_index is None


def test_context_reset() -> None:
    with algopy_testing_context() as context:
        context.any_account(balance=UInt64(1000))
        context.any_asset(name=Bytes(b"TestAsset"), total=UInt64(1000))
        context.any_application(
            approval_program=Bytes(b"TestApp"),
            clear_state_program=Bytes(b"TestClear"),
        )
        context.reset()
        assert len(context._account_data) == 0
        assert len(context._asset_data) == 0
        assert len(context._application_data) == 0
        with pytest.raises(ValueError, match="No inner transaction groups submitted yet!"):
            context.get_submitted_itxn_group(0)
        assert len(context.get_transaction_group()) == 0
        assert len(context._application_logs) == 0
        assert len(context._contracts) == 0
        assert len(context._scratch_spaces) == 0
        assert context._active_transaction_index is None
        assert next(context._asset_id) == 1
        assert next(context._app_id) == 1


def test_algopy_testing_context() -> None:
    with algopy_testing_context() as context:
        assert isinstance(context, AlgopyTestContext)
        assert len(context.get_account_data()) == 1  # reserved for default creator
        context.any_account(balance=UInt64(1000))
        assert len(context.get_account_data()) == 2

    # When called outside of a context manager, it should raise an error
    with pytest.raises(LookupError):
        get_test_context()


def test_get_last_submitted_itxn_loader() -> None:
    with algopy_testing_context() as context:
        itxn1 = PaymentInnerTransaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(1000),
        )
        itxn2 = PaymentInnerTransaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(2000),
        )
        context._append_inner_transaction_group([itxn1, itxn2])
        last_itxn = context.last_submitted_itxn.payment
        assert last_itxn.amount == 2000


def test_clear_inner_transaction_groups() -> None:
    with algopy_testing_context() as context:
        itxn1 = PaymentInnerTransaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(1000),
        )
        itxn2 = PaymentInnerTransaction(
            sender=context.default_creator,
            receiver=context.default_creator,
            amount=UInt64(2000),
        )
        context._append_inner_transaction_group([itxn1, itxn2])
        context.clear_inner_transaction_groups()
        with pytest.raises(ValueError, match="No inner transaction groups submitted yet!"):
            context.get_submitted_itxn_group(0)


def test_misc_global_state_access() -> None:
    with algopy_testing_context() as _:
        contract = GlobalStateValidator()
        contract.validate_g_args(arc4.UInt64(1), arc4.String("TestAsset"))
