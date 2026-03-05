"""Example 03: Logic Signature Gate

This example demonstrates a LogicSig with template variables and Ed25519 signature verification.

Features:
- @logicsig (decorator for LogicSig configuration)
- TemplateVar[Bytes] (compile-time byte constant substitution)
- TemplateVar[UInt64] (compile-time uint64 constant substitution)
- assert (runtime assertion)
- Txn field checks (fee, rekey_to, close_remainder_to)
- op.ed25519verify_bare (Ed25519 signature verification)

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import Bytes, TemplateVar, Txn, UInt64, logicsig, op


@logicsig
def gate() -> bool:
    """The single entry point — returns True to approve the transaction.

    Returns:
        True if all security checks pass.
    """
    # TemplateVar[Bytes] injects a compile-time Ed25519 public key (32 bytes)
    authority_key = TemplateVar[Bytes]("AUTHORITY_KEY")
    # TemplateVar[UInt64] injects a compile-time maximum fee threshold
    max_fee = TemplateVar[UInt64]("MAX_FEE")

    # op.arg(0) retrieves the first argument passed to the logic signature (the signature bytes)
    # op.ed25519verify_bare verifies an Ed25519 signature over raw data (no domain separation)
    # Verifies that the receiver address was signed by the authority key
    assert op.ed25519verify_bare(Txn.receiver.bytes, op.arg(0), authority_key)

    # Assert the transaction fee does not exceed the templated maximum
    assert Txn.fee <= max_fee
    # Assert the transaction cannot rekey the signing account (zero_address = no rekey)
    assert Txn.rekey_to == op.Global.zero_address
    # Assert the transaction cannot close out the remaining balance
    assert Txn.close_remainder_to == op.Global.zero_address

    return True
