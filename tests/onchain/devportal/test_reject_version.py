import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_REJECT_VERSION = EXAMPLES_DIR / "devportal" / "reject_version"
_HELLO_WORLD = EXAMPLES_DIR / "hello_world_arc4"

# call_pinned / call_checked each issue one inner ApplicationCall with fee=0
_INNER_FEE = au.AlgoAmount.from_micro_algo(2000)

_ALWAYS_APPROVE = "#pragma version 10\nint 1"
# approve-all program that also logs an ARC-4 return value: the 0x151f7c75
# ABI return prefix followed by the encoded string "Hello, Upgraded"
_HELLO_UPGRADED = (
    "#pragma version 10\n"
    "pushbytes 0x151f7c75000f48656c6c6f2c205570677261646564\n"
    "log\n"
    "pushint 1"
)


def _deploy(deployer: Deployer) -> tuple[au.AppClient, au.AppClient]:
    """Deploy the RejectVersion contract plus a freshly-created v0 hello target."""
    target = deployer.create(_HELLO_WORLD).client
    reject_version = deployer.create(_REJECT_VERSION).client
    return reject_version, target


def _create_raw_app(
    localnet: au.AlgorandClient, account: au.AddressWithSigners, approval: str
) -> int:
    result = localnet.send.app_create(
        au.AppCreateParams(
            sender=account.addr,
            approval_program=approval,
            clear_state_program=_ALWAYS_APPROVE,
            note=random.randbytes(8),
        )
    )
    app_id = result.app_id
    assert app_id
    return app_id


def _create_upgraded_app(
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
    *,
    updated_approval: str = _ALWAYS_APPROVE,
) -> int:
    """Create a raw approve-all app, then update it once so its version becomes 1."""
    app_id = _create_raw_app(localnet, account, _ALWAYS_APPROVE)
    localnet.send.app_update(
        au.AppUpdateParams(
            sender=account.addr,
            app_id=app_id,
            approval_program=updated_approval,
            clear_state_program=_ALWAYS_APPROVE,
            note=random.randbytes(8),
        )
    )
    return app_id


def test_call_pinned_invokes_target_within_version_pin(deployer: Deployer) -> None:
    reject_version, target = _deploy(deployer)

    # target is v0, so reject_version = max_version + 1 = 1 does not trip
    result = reject_version.send.call(
        au.AppClientMethodCallParams(
            method="call_pinned",
            args=[target.app_id, 0],
            static_fee=_INNER_FEE,
        )
    )
    assert result.abi_return == "Hello, World"


def test_call_checked_rejects_unpatched_target(deployer: Deployer) -> None:
    reject_version, target = _deploy(deployer)

    # the freshly created target is version 0, i.e. still the version declared
    # unsafe, so the minimum-version guard rejects the call
    with pytest.raises((au.LogicError, ValueError), match="target bug has not been patched yet"):
        reject_version.send.call(
            au.AppClientMethodCallParams(
                method="call_checked",
                args=[target.app_id, 0],
                static_fee=_INNER_FEE,
            )
        )


def test_call_pinned_rejects_upgraded_target(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    reject_version = deployer.create(_REJECT_VERSION).client
    # the target has been updated once, so it is now version 1
    target_id = _create_upgraded_app(localnet, account)

    # reject_version = max_version + 1 = 1 and version 1 >= 1, so the AVM
    # rejects the inner call before the target's code runs
    with pytest.raises((au.LogicError, ValueError)):
        reject_version.send.call(
            au.AppClientMethodCallParams(
                method="call_pinned",
                args=[target_id, 0],
                static_fee=_INNER_FEE,
            )
        )


def test_call_pinned_allows_target_at_version_pin_boundary(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    reject_version = deployer.create(_REJECT_VERSION).client
    target_id = _create_upgraded_app(localnet, account, updated_approval=_HELLO_UPGRADED)

    # target version (1) == max_version (1): reject_version = 2 does not trip
    result = reject_version.send.call(
        au.AppClientMethodCallParams(
            method="call_pinned",
            args=[target_id, 1],
            static_fee=_INNER_FEE,
        )
    )
    assert result.abi_return == "Hello, Upgraded"


def test_call_checked_allows_patched_target(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    reject_version = deployer.create(_REJECT_VERSION).client
    # the target has been updated once (version 0 -> 1), i.e. patched past
    # the unsafe version 0, so the guard passes and the inner call runs
    target_id = _create_upgraded_app(localnet, account, updated_approval=_HELLO_UPGRADED)

    result = reject_version.send.call(
        au.AppClientMethodCallParams(
            method="call_checked",
            args=[target_id, 0],
            static_fee=_INNER_FEE,
        )
    )
    assert result.abi_return == "Hello, Upgraded"


def test_call_checked_rejects_target_at_unsafe_version_boundary(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    reject_version = deployer.create(_REJECT_VERSION).client
    target_id = _create_upgraded_app(localnet, account, updated_approval=_HELLO_UPGRADED)

    # target.version (1) is not strictly greater than unsafe_version (1):
    # being AT the unsafe version is still unsafe, so the guard rejects
    with pytest.raises((au.LogicError, ValueError), match="target bug has not been patched yet"):
        reject_version.send.call(
            au.AppClientMethodCallParams(
                method="call_checked",
                args=[target_id, 1],
                static_fee=_INNER_FEE,
            )
        )


def test_call_checked_fails_for_missing_app(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    reject_version = deployer.create(_REJECT_VERSION).client
    # create then delete an app, leaving a dangling app id
    target_id = _create_raw_app(localnet, account, _ALWAYS_APPROVE)
    localnet.send.app_delete(
        au.AppDeleteParams(
            sender=account.addr,
            app_id=target_id,
            note=random.randbytes(8),
        )
    )

    # reading target.version fails because the app no longer exists
    with pytest.raises((au.LogicError, ValueError)):
        reject_version.send.call(
            au.AppClientMethodCallParams(
                method="call_checked",
                args=[target_id, 0],
                static_fee=_INNER_FEE,
            )
        )
