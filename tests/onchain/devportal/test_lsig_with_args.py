import hashlib
import random

import algokit_utils as au
import pytest
from algokit_common import public_key_from_address
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from tests import EXAMPLES_DIR
from tests.test_logic_sig import compile_logic_sig
from tests.utils import arc4_encode

_LSIG_SRC = EXAMPLES_DIR / "devportal" / "lsig_with_args" / "contract.py"
_DUMMY_PK = b"\x00" * 32


def _compile(
    name: str,
    *,
    beneficiary: bytes = _DUMMY_PK,
    payee_a: bytes = _DUMMY_PK,
    payee_b: bytes = _DUMMY_PK,
) -> bytes:
    # all four logicsigs in the file compile together, so every TemplateVar in
    # the module must be supplied on each call (unrelated ones get a dummy)
    return compile_logic_sig(
        _LSIG_SRC,
        name=name,
        template_variables={
            "BENEFICIARY": beneficiary,
            "PAYEE_A": payee_a,
            "PAYEE_B": payee_b,
        },
    )


def _fund(localnet: au.AlgorandClient, account: au.AddressWithSigners, lsig_addr: str) -> None:
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig_addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )


def _pay_from_lsig(
    localnet: au.AlgorandClient,
    lsig: au.LogicSigAccount,
    *,
    receiver: str,
    micro_algo: int,
    note: bytes | None = None,
    lease: bytes | None = None,
    last_valid_round: int | None = None,
) -> au.SendSingleTransactionResult:
    localnet.account.set_signer(lsig.addr, lsig.signer)
    return localnet.send.payment(
        au.PaymentParams(
            sender=lsig.addr,
            receiver=receiver,
            amount=au.AlgoAmount.from_micro_algo(micro_algo),
            note=note,
            lease=lease,
            last_valid_round=last_valid_round,
        )
    )


# --- escrow_release: contract account, single beneficiary baked in via TemplateVar


def test_escrow_release_pays_beneficiary(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    amount = 1_000_000
    bytecode = _compile("escrow_release", beneficiary=public_key_from_address(account.addr))
    lsig = au.LogicSigAccount(logic=bytecode, args=[arc4_encode("uint64", amount)])
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(localnet, lsig, receiver=account.addr, micro_algo=amount)
    assert result.confirmation.confirmed_round is not None


def test_escrow_release_rejects_amount_mismatch(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # the lsig arg pins Txn.amount; paying a different amount must fail
    bytecode = _compile("escrow_release", beneficiary=public_key_from_address(account.addr))
    lsig = au.LogicSigAccount(logic=bytecode, args=[arc4_encode("uint64", 1_000_000)])
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(localnet, lsig, receiver=account.addr, micro_algo=999_999)


def test_escrow_release_rejects_wrong_receiver(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # the beneficiary is baked into the program; paying anyone else must fail
    outsider = localnet.account.random()
    amount = 1_000_000
    bytecode = _compile("escrow_release", beneficiary=public_key_from_address(account.addr))
    lsig = au.LogicSigAccount(logic=bytecode, args=[arc4_encode("uint64", amount)])
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(localnet, lsig, receiver=outsider.addr, micro_algo=amount)


def test_escrow_release_rejects_malformed_arg_encoding(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # default validate_encoding="args" checks the encoded bytes against the
    # declared type: a 7-byte arg is not a valid uint64 encoding
    bytecode = _compile("escrow_release", beneficiary=public_key_from_address(account.addr))
    lsig = au.LogicSigAccount(logic=bytecode, args=[b"\x00" * 7])
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(localnet, lsig, receiver=account.addr, micro_algo=1_000_000)


# --- voucher_redeem: arc4.Struct argument


def _voucher(
    localnet: au.AlgorandClient, recipient: str, max_amount: int
) -> tuple[bytes, bytes, int]:
    """Voucher bytes + the lease and pinned last_valid its redemption requires.

    The lsig enforces `Txn.last_valid == expires_at` and
    `Txn.lease == sha256(voucher_bytes)` (single-use), so expires_at must sit
    inside the node's ~1000-round max validity window.
    """
    expires_at = localnet.get_suggested_params().last_valid
    voucher = arc4_encode(
        "(address,uint64,uint64)",
        (public_key_from_address(recipient), max_amount, expires_at),
    )
    return voucher, hashlib.sha256(voucher).digest(), expires_at


def test_voucher_redeem_within_constraints(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    voucher, lease, expires_at = _voucher(localnet, account.addr, 5_000_000)
    bytecode = _compile("voucher_redeem")
    lsig = au.LogicSigAccount(logic=bytecode, args=[voucher])
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(
        localnet,
        lsig,
        receiver=account.addr,
        micro_algo=1_000_000,
        lease=lease,
        last_valid_round=expires_at,
    )
    assert result.confirmation.confirmed_round is not None


def test_voucher_redeem_is_single_use(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    voucher, lease, expires_at = _voucher(localnet, account.addr, 5_000_000)
    bytecode = _compile("voucher_redeem")
    lsig = au.LogicSigAccount(logic=bytecode, args=[voucher])
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(
        localnet,
        lsig,
        receiver=account.addr,
        micro_algo=1_000_000,
        note=b"first",
        lease=lease,
        last_valid_round=expires_at,
    )
    assert result.confirmation.confirmed_round is not None

    # replaying the same voucher is blocked by the ledger's lease mechanism:
    # the (sender, lease) slot is held until expires_at, and after expires_at
    # the pinned last_valid makes any redemption impossible
    with pytest.raises(TransactionComposerError, match="lease"):
        _pay_from_lsig(
            localnet,
            lsig,
            receiver=account.addr,
            micro_algo=1_000_000,
            note=b"second",
            lease=lease,
            last_valid_round=expires_at,
        )


def test_voucher_redeem_rejects_over_max_amount(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    voucher, lease, expires_at = _voucher(localnet, account.addr, 5_000_000)
    bytecode = _compile("voucher_redeem")
    lsig = au.LogicSigAccount(logic=bytecode, args=[voucher])
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(
            localnet,
            lsig,
            receiver=account.addr,
            micro_algo=5_000_001,
            lease=lease,
            last_valid_round=expires_at,
        )


def test_voucher_redeem_rejects_expired_voucher(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # expires_at is far in the past, so the pinned `Txn.last_valid ==
    # expires_at` check cannot hold for any currently-valid transaction
    voucher = arc4_encode(
        "(address,uint64,uint64)",
        (public_key_from_address(account.addr), 5_000_000, 1),
    )
    bytecode = _compile("voucher_redeem")
    lsig = au.LogicSigAccount(logic=bytecode, args=[voucher])
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(
            localnet,
            lsig,
            receiver=account.addr,
            micro_algo=1_000_000,
            lease=hashlib.sha256(voucher).digest(),
        )


# --- mixed_args: native + arc4 args mixed, returns UInt64


def _mixed_args(receiver_pk: bytes, note: bytes) -> list[bytes]:
    return [
        arc4_encode("uint64", 500_000),
        arc4_encode("address", receiver_pk),
        arc4_encode("byte[]", note),
    ]


def _mixed_args_lease(args: list[bytes]) -> bytes:
    # the lsig requires Txn.lease == sha256(arg0 || arg1 || arg2)
    return hashlib.sha256(b"".join(args)).digest()


def test_mixed_args_succeeds(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> None:
    # the note feeds the lease preimage (sender is the same lsig contract account
    # every run), so it must be unique per run or reruns within the ~1000-round
    # lease validity window are rejected as duplicate (sender, lease) pairs
    note = b"mixed-args-" + random.randbytes(8)
    args = _mixed_args(public_key_from_address(account.addr), note)
    bytecode = _compile("MixedArgsLsig")
    lsig = au.LogicSigAccount(logic=bytecode, args=args)
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(
        localnet,
        lsig,
        receiver=account.addr,
        micro_algo=500_000,
        note=note,
        lease=_mixed_args_lease(args),
    )
    assert result.confirmation.confirmed_round is not None


def test_mixed_args_rejects_wrong_note(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    args = _mixed_args(public_key_from_address(account.addr), b"expected-note")
    bytecode = _compile("MixedArgsLsig")
    lsig = au.LogicSigAccount(logic=bytecode, args=args)
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(
            localnet,
            lsig,
            receiver=account.addr,
            micro_algo=500_000,
            note=b"wrong-note",
            lease=_mixed_args_lease(args),
        )


def test_mixed_args_rejects_missing_lease(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # without the lease committing to the encoded args, the lsig must reject
    note = b"mixed-args-note"
    args = _mixed_args(public_key_from_address(account.addr), note)
    bytecode = _compile("MixedArgsLsig")
    lsig = au.LogicSigAccount(logic=bytecode, args=args)
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(localnet, lsig, receiver=account.addr, micro_algo=500_000, note=note)


# --- escrow_release_to: arc4.Address arg, validate_encoding="unsafe_disabled"


def test_escrow_release_to_pays_approved_payee(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    payee_b = localnet.account.random()
    bytecode = _compile(
        "escrow_release_to",
        payee_a=public_key_from_address(account.addr),
        payee_b=public_key_from_address(payee_b.addr),
    )
    # caller selects PAYEE_A
    lsig = au.LogicSigAccount(
        logic=bytecode,
        args=[arc4_encode("address", public_key_from_address(account.addr))],
    )
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(localnet, lsig, receiver=account.addr, micro_algo=1_000_000)
    assert result.confirmation.confirmed_round is not None


def test_escrow_release_to_pays_second_payee(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    # the caller can select either baked-in payee; here PAYEE_B
    payee_b = localnet.account.random()
    bytecode = _compile(
        "escrow_release_to",
        payee_a=public_key_from_address(account.addr),
        payee_b=public_key_from_address(payee_b.addr),
    )
    lsig = au.LogicSigAccount(
        logic=bytecode,
        args=[arc4_encode("address", public_key_from_address(payee_b.addr))],
    )
    _fund(localnet, account, lsig.addr)

    result = _pay_from_lsig(localnet, lsig, receiver=payee_b.addr, micro_algo=1_000_000)
    assert result.confirmation.confirmed_round is not None


def test_escrow_release_to_rejects_unapproved_payee(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    payee_b = localnet.account.random()
    outsider = localnet.account.random()
    bytecode = _compile(
        "escrow_release_to",
        payee_a=public_key_from_address(account.addr),
        payee_b=public_key_from_address(payee_b.addr),
    )
    # caller passes an address that is not on the allow-list
    lsig = au.LogicSigAccount(
        logic=bytecode,
        args=[arc4_encode("address", public_key_from_address(outsider.addr))],
    )
    _fund(localnet, account, lsig.addr)

    with pytest.raises(TransactionComposerError, match="rejected by logic"):
        _pay_from_lsig(localnet, lsig, receiver=outsider.addr, micro_algo=1_000_000)
