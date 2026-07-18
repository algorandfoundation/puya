from algopy import (
    Account,
    Global,
    TemplateVar,
    TransactionType,
    Txn,
    UInt64,
    arc4,
    logicsig,
    op,
)


# example: LSIG_SIMPLE_ARGS
@logicsig
def escrow_release(amount: UInt64) -> bool:
    """
    A typed lsig for a contract account (escrow): `amount` is auto-decoded
    from `op.arg(0)`, and the default `validate_encoding="args"` verifies
    the encoded bytes against the declared type (see `escrow_release_to`
    for opting out). The beneficiary is baked in via a `TemplateVar`.

    A contract account must constrain every abusable field: `rekey_to` and
    `close_remainder_to` are pinned, and `fee` is bounded — but only per
    transaction, so repeated approved payments can still drain fees. See
    `voucher_redeem` below for the lease-based replay guard.
    """
    beneficiary = TemplateVar[Account]("BENEFICIARY")
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == beneficiary
        and Txn.amount == amount
        and Txn.fee <= Global.min_txn_fee
        and Txn.rekey_to == Global.zero_address
        and Txn.close_remainder_to == Global.zero_address
    )


# example: LSIG_SIMPLE_ARGS


# example: LSIG_STRUCT_ARGS
class Voucher(arc4.Struct):
    """A signed payload describing a single permitted payment."""

    recipient: arc4.Address
    max_amount: arc4.UInt64
    expires_at: arc4.UInt64


@logicsig
def voucher_redeem(voucher: Voucher) -> bool:
    """
    Compound argument types work too. `voucher` is an `arc4.Struct` whose
    fields are decoded and made available as `voucher.recipient`,
    `voucher.max_amount`, `voucher.expires_at`.

    Use case: a holder receives the voucher bytes off-chain and supplies
    them as the lsig arg at redemption time. The lsig verifies that the
    actual payment transaction matches the voucher's constraints.

    Single-use is enforced with a lease: the payment's `lease` must commit
    to the voucher bytes, and `last_valid` is pinned to `expires_at`, so
    once a redemption confirms, the ledger blocks any other transaction
    with the same (sender, lease) pair until `expires_at` has passed — at
    which point the voucher can no longer be valid at all. Without this,
    "max_amount" would only cap each redemption, not the total outflow.

    Note that lsig args are not authenticated by the network — whoever
    submits the transaction chooses them. A production voucher scheme could
    also verify a signature over the encoded voucher bytes (e.g. with
    `op.ed25519verify_bare`) so that only vouchers issued by a trusted key
    can release funds; this example focuses on the struct decoding itself.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == voucher.recipient.native
        and Txn.amount <= voucher.max_amount.as_uint64()
        # pin the validity window's end to the voucher expiry...
        and Txn.last_valid == voucher.expires_at.as_uint64()
        # ...and hold the (sender, lease) slot until then: one redemption only
        and Txn.lease == op.sha256(voucher.bytes)
        and Txn.fee <= Global.min_txn_fee
        and Txn.rekey_to == Global.zero_address
        and Txn.close_remainder_to == Global.zero_address
    )


# example: LSIG_STRUCT_ARGS


# example: LSIG_MIXED_ARGS
@logicsig(name="MixedArgsLsig", avm_version=11)
def mixed_args(
    amount: UInt64,
    recipient: arc4.Address,
    note: arc4.DynamicBytes,
) -> UInt64:
    """
    A logic signature can return `UInt64` instead of `bool`; a non-zero value
    is treated as success. Native (`UInt64`) and ARC-4 (`arc4.Address`,
    `arc4.DynamicBytes`) argument types can be mixed freely. `op.arg(N)`
    remains callable inside the body for raw access to the encoded bytes.

    Decorator options like `name=` and `avm_version=` configure how puya
    compiles the lsig itself; they do not become function parameters.
    """
    assert Txn.type_enum == TransactionType.Payment
    assert Txn.receiver == recipient.native
    assert Txn.amount >= amount
    assert Txn.note == note.native
    assert Txn.fee <= Global.min_txn_fee
    assert Txn.rekey_to == Global.zero_address
    assert Txn.close_remainder_to == Global.zero_address

    # raw access via op.arg(N): require the payment's lease to commit to the
    # hash of all three encoded arguments, so no other transaction can reuse
    # the same (sender, lease) slot during this transaction's validity window
    digest = op.sha256(op.arg(0) + op.arg(1) + op.arg(2))
    assert Txn.lease == digest
    return UInt64(1)


# example: LSIG_MIXED_ARGS


# example: LSIG_UNSAFE_ARGS
@logicsig(validate_encoding="unsafe_disabled")
def escrow_release_to(payee: arc4.Address) -> bool:
    """
    `validate_encoding="unsafe_disabled"` skips the ARC-4 encoding checks on
    decode, trading a small amount of safety for smaller bytecode. It is safe
    here because any 32-byte sequence is a valid `arc4.Address` encoding, so
    there is nothing for the check to reject.

    This escrow releases funds to either of two beneficiaries baked in at
    compile time; the caller selects which one via the `payee` argument.
    Disabling the *encoding* check does not weaken the *authorization* check —
    the chosen payee is still verified against the baked-in allow-list and the
    transaction is fully constrained below.
    """
    payee_a = TemplateVar[Account]("PAYEE_A")
    payee_b = TemplateVar[Account]("PAYEE_B")
    recipient = payee.native
    return (
        Txn.type_enum == TransactionType.Payment
        and recipient in (payee_a, payee_b)
        and Txn.receiver == recipient
        and Txn.fee <= Global.min_txn_fee
        and Txn.rekey_to == Global.zero_address
        and Txn.close_remainder_to == Global.zero_address
    )


# example: LSIG_UNSAFE_ARGS
