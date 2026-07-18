import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_REFERENCE_APP = EXAMPLES_DIR / "devportal" / "reference_app"

# each call issues one inner ApplicationCall with fee=0
_INNER_FEE = au.AlgoAmount.from_micro_algo(2000)

_ALWAYS_APPROVE = "#pragma version 10\nint 1"


def _deploy_reference(deployer: Deployer, known_app_id: int) -> au.AppClient:
    """Deploy ReferenceApp with the TMPL_KNOWN_APP template variable filled."""
    spec = compile_arc56(_REFERENCE_APP / "contract.py", contract_name="ReferenceApp")
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
            deploy_time_params={"TMPL_KNOWN_APP": known_app_id}
        ),
    )
    return client


def test_increment_via_inner_known_app(deployer: Deployer) -> None:
    """The template-provided Counter is incremented by the no-arg variant."""
    counter = deployer.create((_REFERENCE_APP / "contract.py", "Counter")).client
    reference = _deploy_reference(deployer, counter.app_id)

    def increment() -> object:
        return reference.send.call(
            au.AppClientMethodCallParams(
                method="increment_via_inner",
                static_fee=_INNER_FEE,
                app_references=[counter.app_id],
                note=random.randbytes(8),
            )
        ).abi_return

    assert increment() == 1
    assert increment() == 2


def test_increment_via_inner_known_app_deleted_fails(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    """A deleted app id no longer resolves, so the inner call fails."""
    created = localnet.send.app_create(
        au.AppCreateParams(
            sender=account.addr,
            approval_program=_ALWAYS_APPROVE,
            clear_state_program=_ALWAYS_APPROVE,
            note=random.randbytes(8),
        )
    )
    app_id = created.app_id
    assert app_id
    localnet.send.app_delete(
        au.AppDeleteParams(sender=account.addr, app_id=app_id, note=random.randbytes(8))
    )
    reference = _deploy_reference(deployer, app_id)

    with pytest.raises(au.LogicError):
        reference.send.call(
            au.AppClientMethodCallParams(
                method="increment_via_inner",
                static_fee=_INNER_FEE,
                app_references=[app_id],
            )
        )


def test_increment_via_inner_with_arg(deployer: Deployer) -> None:
    # deploy the Counter callee and the ReferenceApp caller; the template value
    # is irrelevant for the with-arg variant but must be supplied to deploy
    counter = deployer.create((_REFERENCE_APP / "contract.py", "Counter")).client
    reference = _deploy_reference(deployer, counter.app_id)

    def increment() -> object:
        # note keeps otherwise-identical txns unique
        return reference.send.call(
            au.AppClientMethodCallParams(
                method="increment_via_inner_with_arg",
                args=[counter.app_id],
                static_fee=_INNER_FEE,
                app_references=[counter.app_id],
                note=random.randbytes(8),
            )
        ).abi_return

    # the inner call bumps Counter.counter and returns the new value
    assert increment() == 1
    assert increment() == 2
    assert increment() == 3


def test_increment_via_inner_with_arg_rejects_non_counter_app(
    deployer: Deployer,
) -> None:
    # pointing at an app that is not a Counter fails the inner abi_call dispatch
    reference = _deploy_reference(deployer, 0)

    with pytest.raises(au.LogicError):
        reference.send.call(
            au.AppClientMethodCallParams(
                method="increment_via_inner_with_arg",
                args=[reference.app_id],  # not a Counter
                static_fee=_INNER_FEE,
                app_references=[reference.app_id],
            )
        )
