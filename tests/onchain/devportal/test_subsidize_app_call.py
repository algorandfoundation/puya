import algokit_utils as au
import pytest
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from tests import EXAMPLES_DIR
from tests.test_logic_sig import compile_logic_sig
from tests.utils.deployer import Deployer

_SUBSIDIZE = EXAMPLES_DIR / "devportal" / "subsidize_app_call" / "contract.py"
_HELLO_WORLD = EXAMPLES_DIR / "hello_world_arc4"

_MIN_FEE = 1000


def _compile(genesis_hash: bytes, expiration_round: int, known_app: int) -> bytes:
    return compile_logic_sig(
        _SUBSIDIZE,
        template_variables={
            "TARGET_NETWORK_GENESIS": genesis_hash,
            "EXPIRATION_ROUND": expiration_round,
            "KNOWN_APP": known_app,
        },
    )


def _genesis_and_round(localnet: au.AlgorandClient) -> tuple[bytes, int]:
    params = localnet.get_suggested_params()
    return params.genesis_hash, params.last_valid


def _fund_lsig(
    localnet: au.AlgorandClient, account: au.AddressWithSigners, lsig: au.LogicSigAccount
) -> None:
    localnet.account.set_signer(lsig.addr, lsig.signer)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=lsig.addr,
            amount=au.AlgoAmount.from_algo(1),
        )
    )


def test_subsidize_authorizes_fee_for_known_app_call(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    # group: [app call to KNOWN_APP with fee=0, self-payment from lsig with fee=2*min]
    result = (
        localnet.new_group()
        .add_app_call_method_call(
            target.params.call(
                au.AppClientMethodCallParams(
                    method="hello",
                    args=["subsidized"],
                    static_fee=au.AlgoAmount.from_micro_algo(0),
                )
            )
        )
        .add_payment(
            au.PaymentParams(
                sender=lsig.addr,
                receiver=lsig.addr,
                amount=au.AlgoAmount.from_micro_algo(0),
                static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
            )
        )
        .send()
    )
    assert result.confirmations[-1].confirmed_round is not None
    assert result.returns[0].value == "Hello, subsidized"


def test_subsidize_rejects_unknown_app(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    other = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    # lsig is pinned to `target`, but the group calls `other`
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_app_call_method_call(
                other.params.call(
                    au.AppClientMethodCallParams(
                        method="hello",
                        args=["x"],
                        static_fee=au.AlgoAmount.from_micro_algo(0),
                    )
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                    static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
                )
            )
            .send()
        )


def test_subsidize_rejects_when_app_call_pays_own_fee(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    # the lsig requires the preceding app call's fee to be 0, so a self-paying
    # app call must be rejected
    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_app_call_method_call(
                target.params.call(
                    au.AppClientMethodCallParams(
                        method="hello",
                        args=["x"],
                        static_fee=au.AlgoAmount.from_micro_algo(_MIN_FEE),
                    )
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                    static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
                )
            )
            .send()
        )


def test_subsidize_rejects_wrong_fee(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    # lsig payment fee must be exactly 2 * min_txn_fee
    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_app_call_method_call(
                target.params.call(
                    au.AppClientMethodCallParams(
                        method="hello",
                        args=["x"],
                        static_fee=au.AlgoAmount.from_micro_algo(0),
                    )
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                    static_fee=au.AlgoAmount.from_micro_algo(3 * _MIN_FEE),
                )
            )
            .send()
        )


def test_subsidize_rejects_when_preceding_txn_not_app_call(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    # the typed gtxn parameter's implicit type assertion fails outright when
    # the preceding group transaction is a Payment rather than an app call
    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_payment(
                au.PaymentParams(
                    sender=account.addr,
                    receiver=account.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                    static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
                )
            )
            .send()
        )


def test_subsidize_rejects_nonzero_amount(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    bytecode = _compile(genesis_hash, last_round + 1000, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    # the lsig payment must be an empty self-payment (Txn.amount == 0)
    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_app_call_method_call(
                target.params.call(
                    au.AppClientMethodCallParams(
                        method="hello",
                        args=["x"],
                        static_fee=au.AlgoAmount.from_micro_algo(0),
                    )
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(1),
                    static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
                )
            )
            .send()
        )


def test_subsidize_rejects_expired_lsig(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    target = deployer.create(_HELLO_WORLD).client
    genesis_hash, last_round = _genesis_and_round(localnet)
    # EXPIRATION_ROUND is far in the past, so Txn.last_valid <= EXPIRATION fails
    bytecode = _compile(genesis_hash, 1, target.app_id)

    lsig = au.LogicSigAccount(logic=bytecode)
    _fund_lsig(localnet, account, lsig)

    with pytest.raises((au.LogicError, TransactionComposerError)):
        (
            localnet.new_group()
            .add_app_call_method_call(
                target.params.call(
                    au.AppClientMethodCallParams(
                        method="hello",
                        args=["x"],
                        static_fee=au.AlgoAmount.from_micro_algo(0),
                    )
                )
            )
            .add_payment(
                au.PaymentParams(
                    sender=lsig.addr,
                    receiver=lsig.addr,
                    amount=au.AlgoAmount.from_micro_algo(0),
                    static_fee=au.AlgoAmount.from_micro_algo(2 * _MIN_FEE),
                )
            )
            .send()
        )
