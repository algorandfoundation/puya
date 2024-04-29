from algopy import Bytes, TemplateVar, UInt64, gtxn, logicsig, subroutine
from algopy.op import Global


@logicsig
def pre_approved_sale() -> bool:
    """
    Allows for pre-authorising the sale of an asset for a pre-determined price, but to an
    undetermined buyer.

    The checks here are not meant to be exhaustive
    """
    pay_txn = gtxn.PaymentTransaction(0)
    asset_txn = gtxn.AssetTransferTransaction(1)
    assert_correct_payment(pay_txn)
    assert_correct_asset(asset_txn)
    assert pay_txn.sender == asset_txn.asset_receiver
    assert Global.group_size == 2
    return True


@logicsig(name="always_allow")
def some_sig() -> bool:
    return True


@subroutine
def assert_correct_payment(txn: gtxn.PaymentTransaction) -> None:
    assert txn.receiver.bytes == TemplateVar[Bytes]("SELLER") and (
        txn.amount == TemplateVar[UInt64]("PRICE")
    )


@subroutine
def assert_correct_asset(txn: gtxn.AssetTransferTransaction) -> None:
    assert (
        txn.asset_amount == 1
        and txn.sender.bytes == TemplateVar[Bytes]("SELLER")
        and txn.xfer_asset.id == TemplateVar[UInt64]("ASSET_ID")
        and txn.asset_close_to == Global.zero_address
        and txn.rekey_to == Global.zero_address
    )
