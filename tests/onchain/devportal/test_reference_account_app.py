import random

import algokit_utils as au
import pytest
from algokit_common import public_key_from_address

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_REFERENCE_ACCOUNT_APP = EXAMPLES_DIR / "devportal" / "reference_account_app"


def _deploy_ref(deployer: Deployer, known_account: str, known_app_id: int) -> au.AppClient:
    """Deploy ReferenceAccountApp with both template variables filled."""
    spec = compile_arc56(_REFERENCE_ACCOUNT_APP, contract_name="ReferenceAccountApp")
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
            deploy_time_params={
                "TMPL_KNOWN_ACCOUNT": public_key_from_address(known_account),
                "TMPL_KNOWN_APP": known_app_id,
            }
        ),
    )
    return client


def _opt_in(client: au.AppClient, signer: au.AddressWithSigners) -> None:
    """Opt the given account into the MyCounter app via its OptIn ABI method."""
    client.send.call(
        au.AppClientMethodCallParams(
            method="opt_in",
            on_complete=au.OnApplicationComplete.OptIn,
            sender=signer.addr,
            signer=signer.signer,
            note=random.randbytes(8),
        )
    )


def _increment(client: au.AppClient, signer: au.AddressWithSigners) -> object:
    return client.send.call(
        au.AppClientMethodCallParams(
            method="increment_my_counter",
            sender=signer.addr,
            signer=signer.signer,
            note=random.randbytes(8),
        )
    ).abi_return


def test_increment_my_counter_tracks_per_account(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    """MyCounter increments the opted-in caller's local counter on each call."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client

    _opt_in(counter, account)
    assert _increment(counter, account) == 1
    assert _increment(counter, account) == 2
    assert _increment(counter, account) == 3


def test_increment_without_opt_in_fails(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    """Calling increment without opting in trips the is_opted_in assertion."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client

    with pytest.raises(au.LogicError, match="Account is not opted in to the app"):
        _increment(counter, account)


def test_get_my_counter_with_arg_reads_other_apps_local_state(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    """ReferenceAccountApp reads the per-account counter from a separate app."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client
    ref = _deploy_ref(deployer, account.addr, counter.app_id)

    _opt_in(counter, account)
    _increment(counter, account)
    _increment(counter, account)

    result = ref.send.call(
        au.AppClientMethodCallParams(
            method="get_my_counter_with_arg",
            args=[account.addr, counter.app_id],
        )
    )
    assert result.abi_return == 2


def test_get_my_counter_with_arg_not_opted_in_fails(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """Reading a counter for an account that never opted in fails inside the
    `app_local_get_ex` opcode itself, *before* the contract's `exists` assert
    is ever reached. Note: algokit maps the failing PC to the nearest ARC-56
    error message, so the *reported text* is still the assert's message — the
    trace line (`app_local_get_ex <-- Error`) is what identifies the real
    failure point."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client
    ref = _deploy_ref(deployer, account.addr, counter.app_id)

    not_opted = localnet.account.random()
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=not_opted.addr,
            amount=au.AlgoAmount.from_algo(1),
            note=random.randbytes(8),
        )
    )

    with pytest.raises(au.LogicError, match="app_local_get_ex"):
        ref.send.call(
            au.AppClientMethodCallParams(
                method="get_my_counter_with_arg",
                args=[not_opted.addr, counter.app_id],
            )
        )


def test_get_my_counter_with_arg_key_missing_fails(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """`exists` is False only when the account IS opted in but the key was
    never written — that is the case the contract's assert actually guards."""
    ref = _deploy_ref(deployer, account.addr, 0)

    # a raw app with a local-state schema whose opt-in writes nothing, so the
    # opted-in account has no "my_counter" key
    raw = localnet.send.app_create(
        au.AppCreateParams(
            sender=account.addr,
            approval_program="#pragma version 10\nint 1",
            clear_state_program="#pragma version 10\nint 1",
            schema=au.AppCreateSchema(
                global_ints=0, global_byte_slices=0, local_ints=1, local_byte_slices=0
            ),
            note=random.randbytes(8),
        )
    )
    assert raw.app_id
    localnet.send.app_call(
        au.AppCallParams(
            sender=account.addr,
            app_id=raw.app_id,
            on_complete=au.OnApplicationComplete.OptIn,
            note=random.randbytes(8),
        )
    )

    with pytest.raises(au.LogicError, match="my_counter is not set for this account"):
        ref.send.call(
            au.AppClientMethodCallParams(
                method="get_my_counter_with_arg",
                args=[account.addr, raw.app_id],
            )
        )


def test_get_my_counter_known_pair(deployer: Deployer, account: au.AddressWithSigners) -> None:
    """The template-provided account/app pair's counter is read by the no-arg variant."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client
    _opt_in(counter, account)
    _increment(counter, account)
    ref = _deploy_ref(deployer, account.addr, counter.app_id)

    result = ref.send.call(au.AppClientMethodCallParams(method="get_my_counter"))
    assert result.abi_return == 1


def test_get_my_counter_known_pair_not_opted_in_fails(
    deployer: Deployer, account: au.AddressWithSigners, localnet: au.AlgorandClient
) -> None:
    """A template-provided account that never opted in to the known app fails
    inside the `app_local_get_ex` opcode (see the note on the with-arg variant
    about how the error is reported)."""
    counter = deployer.create((_REFERENCE_ACCOUNT_APP, "MyCounter")).client
    not_opted = localnet.account.random()
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=not_opted.addr,
            amount=au.AlgoAmount.from_algo(1),
            note=random.randbytes(8),
        )
    )
    ref = _deploy_ref(deployer, not_opted.addr, counter.app_id)

    with pytest.raises(au.LogicError, match="app_local_get_ex"):
        ref.send.call(au.AppClientMethodCallParams(method="get_my_counter"))
