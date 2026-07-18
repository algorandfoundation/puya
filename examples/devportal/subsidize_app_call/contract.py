from algopy import (
    Application,
    Bytes,
    Global,
    TemplateVar,
    Txn,
    UInt64,
    gtxn,
    logicsig,
)


# example: LSIG_SUBSIDIZEAPPCALL
@logicsig
def subsidize_app_call(prev_call: gtxn.ApplicationCallTransaction) -> bool:
    """
    This Contract Account will subsidize the fees for any AppCall transaction directed to a known
    application.

    Transaction-typed logicsig parameters bind positionally to the transactions
    immediately *preceding* the signed transaction in the group (they are not
    passed via the args array): `prev_call` here is the transaction at
    `Txn.group_index - 1`, and the compiler asserts its type is ApplicationCall.
    """

    # this will assert the current transaction is a payment
    # it's exactly equivalent to using the `Txn` object,
    # just a bit more explicit
    current_txn = gtxn.PaymentTransaction(Txn.group_index)
    return (
        # is it safe to pay for the fees of the previous transaction?
        current_txn.receiver == current_txn.sender
        and current_txn.amount == 0
        and current_txn.rekey_to == Global.zero_address
        and current_txn.close_remainder_to == Global.zero_address
        and current_txn.fee == 2 * Global.min_txn_fee
        and current_txn.last_valid <= TemplateVar[UInt64]("EXPIRATION_ROUND")
        and Global.genesis_hash == TemplateVar[Bytes]("TARGET_NETWORK_GENESIS")
        # does the previous transaction (already asserted to be an app call by
        # the typed parameter) target the known app, paying no fee itself?
        and prev_call.app_id == TemplateVar[Application]("KNOWN_APP")
        and prev_call.fee == 0
    )


# example: LSIG_SUBSIDIZEAPPCALL
