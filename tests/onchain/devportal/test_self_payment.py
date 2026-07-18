import hashlib

import algokit_utils as au
import pytest
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from tests import EXAMPLES_DIR
from tests.test_logic_sig import compile_logic_sig

_SELF_PAYMENT = EXAMPLES_DIR / "devportal" / "self_payment" / "contract.py"

# the lsig requires Txn.lease == op.sha256(b"self-payment")
_LEASE = hashlib.sha256(b"self-payment").digest()


def _compile(genesis_hash: bytes, last_round: int) -> bytes:
    return compile_logic_sig(
        _SELF_PAYMENT,
        template_variables={
            "TARGET_NETWORK_GENESIS": genesis_hash,
            "LAST_ROUND": last_round,
        },
    )


def _genesis_and_round(localnet: au.AlgorandClient) -> tuple[bytes, int]:
    params = localnet.get_suggested_params()
    return params.genesis_hash, params.last_valid


def test_self_payment_authorizes_empty_self_payment(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(1),
        )
    )

    # an empty self-payment with the expected lease, fee and last_valid round
    result = localnet.send.payment(
        au.PaymentParams(
            sender=lsig.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_micro_algo(0),
            lease=_LEASE,
            last_valid_round=last_round,
            static_fee=au.AlgoAmount.from_micro_algo(1000),
        )
    )
    assert result.confirmation.confirmed_round is not None


def test_self_payment_rejects_nonzero_amount(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # Txn.amount == 0 is required by the lsig
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(1),
                lease=_LEASE,
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(1000),
            )
        )


def test_self_payment_rejects_wrong_receiver(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # Txn.receiver must equal Txn.sender; paying to another account is rejected
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=account.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                lease=_LEASE,
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(1000),
            )
        )


def test_self_payment_rejects_missing_lease(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # without the expected lease the lsig rejects the transaction
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(1000),
            )
        )


def test_self_payment_rejects_wrong_fee(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # Txn.fee must be exactly Global.min_txn_fee
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                lease=_LEASE,
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(2000),
            )
        )


def test_self_payment_rejects_rekey(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # Txn.rekey_to must be the zero address; rekeying away is rejected
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                rekey_to=account.addr,
                lease=_LEASE,
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(1000),
            )
        )


def test_self_payment_rejects_wrong_last_round(
    localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    genesis_hash, last_round = _genesis_and_round(localnet)
    # compile pinned to a LAST_ROUND that the actual txn will not match
    bytecode = _compile(genesis_hash, last_round + 500)

    lsig = au.LogicSigAccount(logic=bytecode)
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(2),
        )
    )

    # Txn.last_valid must equal the pinned LAST_ROUND template var
    with pytest.raises((au.LogicError, TransactionComposerError)):
        localnet.send.payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                lease=_LEASE,
                last_valid_round=last_round,
                static_fee=au.AlgoAmount.from_micro_algo(1000),
            )
        )
