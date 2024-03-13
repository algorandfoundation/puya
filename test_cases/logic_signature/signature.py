from puyapy import Bytes, TemplateVar, TransactionType, UInt64, logicsig, subroutine
from puyapy.op import GTxn


@logicsig
def pre_approved_sale() -> bool:
    """
    Allows for pre-authorising the sale of an asset for a pre-determined price, but to an
    undetermined buyer.

    The checks here are not meant to be exhaustive
    """
    assert_correct_payment(txn_offset=UInt64(0))
    assert_correct_asset(txn_offset=UInt64(1))
    assert GTxn.sender(UInt64(0)) == GTxn.asset_receiver(UInt64(1))
    return True


@logicsig(name="always_allow")
def some_sig() -> bool:
    return True


@subroutine
def assert_correct_payment(txn_offset: UInt64) -> None:
    assert (
        GTxn.type_enum(txn_offset) == TransactionType.Payment
        and GTxn.receiver(txn_offset).bytes == TemplateVar[Bytes]("SELLER")
        and GTxn.amount(txn_offset) == TemplateVar[UInt64]("PRICE")
    )


@subroutine
def assert_correct_asset(txn_offset: UInt64) -> None:
    assert (
        GTxn.type_enum(txn_offset) == TransactionType.AssetTransfer
        and GTxn.asset_amount(txn_offset) == 1
        and GTxn.sender(txn_offset).bytes == TemplateVar[Bytes]("SELLER")
        and GTxn.xfer_asset(txn_offset).id == TemplateVar[UInt64]("ASSET_ID")
    )
