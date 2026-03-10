import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context
from contract import gate
from nacl.signing import SigningKey

SIGNING_KEY = SigningKey.generate()
AUTHORITY_PUBKEY = bytes(SIGNING_KEY.verify_key)
MAX_FEE = 10_000


def _setup_and_execute(
    ctx: AlgopyTestContext,
    *,
    fee: int = 1000,
    rekey_to: algopy.Account | None = None,
    close_remainder_to: algopy.Account | None = None,
    signature: bytes | None = None,
) -> bool | algopy.UInt64:
    ctx.set_template_var("AUTHORITY_KEY", algopy.Bytes(AUTHORITY_PUBKEY))
    ctx.set_template_var("MAX_FEE", algopy.UInt64(MAX_FEE))

    receiver = ctx.any.account()
    zero = algopy.Account(algopy.op.Global.zero_address.bytes)

    if signature is None:
        receiver_bytes = receiver.bytes.value
        signature = SIGNING_KEY.sign(receiver_bytes).signature

    pay_txn = ctx.any.txn.payment(
        receiver=receiver,
        fee=algopy.UInt64(fee),
        rekey_to=rekey_to or zero,
        close_remainder_to=close_remainder_to or zero,
    )

    with ctx.txn.create_group(gtxns=[pay_txn], active_txn_index=0):
        return ctx.execute_logicsig(gate, algopy.Bytes(signature))


def test_gate_approves_valid_payment():
    with algopy_testing_context() as ctx:
        result = _setup_and_execute(ctx)
        assert result


def test_gate_rejects_excessive_fee():
    with algopy_testing_context() as ctx, pytest.raises(AssertionError):
        _setup_and_execute(ctx, fee=MAX_FEE + 1)


def test_gate_rejects_rekey():
    with algopy_testing_context() as ctx:
        rekey_target = ctx.any.account()
        with pytest.raises(AssertionError):
            _setup_and_execute(ctx, rekey_to=rekey_target)


def test_gate_rejects_close_remainder():
    with algopy_testing_context() as ctx:
        close_target = ctx.any.account()
        with pytest.raises(AssertionError):
            _setup_and_execute(ctx, close_remainder_to=close_target)


def test_gate_rejects_invalid_signature():
    with algopy_testing_context() as ctx, pytest.raises(AssertionError):
        _setup_and_execute(ctx, signature=b"\x00" * 64)
