import hashlib
import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_OP_BUDGET = EXAMPLES_DIR / "devportal" / "op_budget"

# generous flat fee to cover the chain of inner OpUp application calls
_FEE = au.AlgoAmount.from_micro_algo(20_000)


def _params(method: str, *args: object, fee: au.AlgoAmount = _FEE) -> au.AppClientMethodCallParams:
    return au.AppClientMethodCallParams(
        method=method, args=list(args), static_fee=fee, note=random.randbytes(8)
    )


def _expected_digest(seed: bytes, rounds: int) -> bytes:
    """Mirror of the contract: chained sha256 applied `rounds` times."""
    digest = seed
    for _ in range(rounds):
        digest = hashlib.sha256(digest).digest()
    return digest


def test_many_hashes_group_credit(deployer: Deployer) -> None:
    client = deployer.create(_OP_BUDGET).client
    seed = b"seed"
    rounds = 20
    # ensure_budget covers the extra ops; the static fee pays the inner OpUps
    result = client.send.call(_params("many_hashes_group_credit", seed, rounds))
    assert result.abi_return == _expected_digest(seed, rounds)


def test_many_hashes_default_fee_source(deployer: Deployer) -> None:
    # `many_hashes` uses the default GroupCredit fee source
    client = deployer.create(_OP_BUDGET).client
    seed = b"hello world"
    rounds = 20
    result = client.send.call(_params("many_hashes", seed, rounds))
    assert result.abi_return == _expected_digest(seed, rounds)


def test_many_hashes_any_fee_source(deployer: Deployer) -> None:
    client = deployer.create(_OP_BUDGET).client
    seed = b"abc"
    rounds = 25
    result = client.send.call(_params("many_hashes_any", seed, rounds))
    assert result.abi_return == _expected_digest(seed, rounds)


def test_many_hashes_app_pays(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = deployer.create(_OP_BUDGET).client

    # AppAccount fee source: the application account itself pays inner OpUp fees,
    # so it must hold algos.
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_algo(1),
        )
    )

    seed = b"app pays"
    rounds = 20
    # the app account pays the inner fees, so the outer txn only needs the
    # standard min fee
    result = client.send.call(
        _params(
            "many_hashes_app_pays",
            seed,
            rounds,
            fee=au.AlgoAmount.from_micro_algo(1_000),
        )
    )
    assert result.abi_return == _expected_digest(seed, rounds)


def test_many_hashes_multiple_op_ups(deployer: Deployer) -> None:
    # rounds=100 requires ~4100 ops of budget, i.e. several chained OpUp
    # inner calls on top of the base 700
    client = deployer.create(_OP_BUDGET).client
    seed = b"lots of hashing"
    rounds = 100
    result = client.send.call(_params("many_hashes", seed, rounds))
    assert result.abi_return == _expected_digest(seed, rounds)


def test_many_hashes_zero_rounds(deployer: Deployer) -> None:
    # with rounds=0 the loop never runs and the seed is returned unchanged
    client = deployer.create(_OP_BUDGET).client
    seed = b"unchanged"
    result = client.send.call(_params("many_hashes", seed, 0))
    assert result.abi_return == seed


def test_many_hashes_group_credit_without_credit_fails(deployer: Deployer) -> None:
    # GroupCredit inner OpUp calls carry fee=0 and rely on excess fee paid by
    # the group; with only the min fee on the outer txn there is no credit
    client = deployer.create(_OP_BUDGET).client
    with pytest.raises((au.LogicError, ValueError)):
        client.send.call(
            _params(
                "many_hashes",
                b"seed",
                20,
                fee=au.AlgoAmount.from_micro_algo(1_000),
            )
        )


def test_many_hashes_app_pays_unfunded_fails(deployer: Deployer) -> None:
    # AppAccount fee source with no algos in the app account cannot pay the
    # inner OpUp fees, so the call fails
    client = deployer.create(_OP_BUDGET).client
    with pytest.raises(au.LogicError):
        client.send.call(
            _params(
                "many_hashes_app_pays",
                b"seed",
                20,
                fee=au.AlgoAmount.from_micro_algo(1_000),
            )
        )
