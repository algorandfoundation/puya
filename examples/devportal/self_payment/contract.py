from algopy import (
    Bytes,
    Global,
    TemplateVar,
    Txn,
    UInt64,
    gtxn,
    logicsig,
    op,
)


# example: LSIG_SELFPAYMENT
@logicsig
def self_payment() -> bool:
    """
    This Delegated Account will authorize a single empty self payment,
    valid no later than a round known ahead of time.
    """

    current_txn = gtxn.PaymentTransaction(Txn.group_index)
    return (
        current_txn.receiver == current_txn.sender
        and current_txn.amount == 0
        and current_txn.rekey_to == Global.zero_address
        and current_txn.close_remainder_to == Global.zero_address
        and current_txn.fee == Global.min_txn_fee
        and Global.genesis_hash == TemplateVar[Bytes]("TARGET_NETWORK_GENESIS")
        # Pinning last_valid and requiring a non-empty lease prevents replay attacks:
        # once confirmed, the (sender, lease) pair is locked until LAST_ROUND passes.
        and current_txn.last_valid == TemplateVar[UInt64]("LAST_ROUND")
        and current_txn.lease == op.sha256(b"self-payment")
    )


# example: LSIG_SELFPAYMENT
