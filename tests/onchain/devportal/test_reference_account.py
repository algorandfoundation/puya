import random

import algokit_utils as au
import pytest
from algokit_common import public_key_from_address

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_REFERENCE_ACCOUNT = EXAMPLES_DIR / "devportal" / "reference_account"


def _deploy(deployer: Deployer, known_account: str) -> au.AppClient:
    """Deploy ReferenceAccount with the TMPL_KNOWN_ACCOUNT template variable filled."""
    spec = compile_arc56(_REFERENCE_ACCOUNT)
    factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=deployer.localnet,
            app_spec=spec,
            default_sender=deployer.account.addr,
        )
    )
    client, _ = factory.send.bare.create(
        au.AppFactoryCreateParams(note=random.randbytes(8)),
        compilation_params=au.AppClientCompilationParams(
            deploy_time_params={"TMPL_KNOWN_ACCOUNT": public_key_from_address(known_account)}
        ),
    )
    return client


def test_known_account_balance(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """The template-provided account's balance is read by the no-arg variant."""
    funded = localnet.account.random()
    fund_amount = au.AlgoAmount.from_algo(5)
    localnet.send.payment(
        au.PaymentParams(sender=account.addr, receiver=funded.addr, amount=fund_amount)
    )
    client = _deploy(deployer, funded.addr)

    result = client.send.call(au.AppClientMethodCallParams(method="get_account_balance"))
    assert result.abi_return == fund_amount.micro_algo


def test_known_account_unfunded_fails(deployer: Deployer, localnet: au.AlgorandClient) -> None:
    """Reading `.balance` of an unfunded account triggers the AVM
    `acct_params_get AcctBalance` funded assertion, so the call fails."""
    client = _deploy(deployer, localnet.account.random().addr)

    with pytest.raises(au.LogicError, match="account funded"):
        client.send.call(au.AppClientMethodCallParams(method="get_account_balance"))


def test_with_argument_reads_funded_account_balance(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """A funded account's real balance is read via the with-argument variant."""
    client = _deploy(deployer, deployer.account.addr)

    funded = localnet.account.random()
    fund_amount = au.AlgoAmount.from_algo(7)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=funded.addr,
            amount=fund_amount,
        )
    )

    result = client.send.call(
        au.AppClientMethodCallParams(
            method="get_account_balance_with_arg",
            args=[funded.addr],
        )
    )
    assert result.abi_return == fund_amount.micro_algo


def test_with_argument_unfunded_account_fails(
    deployer: Deployer, localnet: au.AlgorandClient
) -> None:
    """An unfunded account has no balance entry, so `.balance` asserts."""
    client = _deploy(deployer, deployer.account.addr)

    fresh = localnet.account.random()
    with pytest.raises(au.LogicError, match="account funded"):
        client.send.call(
            au.AppClientMethodCallParams(
                method="get_account_balance_with_arg",
                args=[fresh.addr],
            )
        )


def test_balance_tracks_repeated_funding(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """The reported balance grows as the account receives more payments."""
    client = _deploy(deployer, deployer.account.addr)

    target = localnet.account.random()

    def balance() -> object:
        return client.send.call(
            au.AppClientMethodCallParams(
                method="get_account_balance_with_arg",
                args=[target.addr],
                note=random.randbytes(8),
            )
        ).abi_return

    first = au.AlgoAmount.from_algo(3)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=target.addr,
            amount=first,
            note=random.randbytes(8),
        )
    )
    assert balance() == first.micro_algo

    second = au.AlgoAmount.from_algo(2)
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=target.addr,
            amount=second,
            note=random.randbytes(8),
        )
    )
    assert balance() == first.micro_algo + second.micro_algo
