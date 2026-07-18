import random

import algokit_utils as au
import pytest
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_ABIMETHOD_OPTIONS = EXAMPLES_DIR / "devportal" / "abimethod_options"


def _create(deployer: Deployer, governor: str, fee_asset: int) -> au.AppClient:
    return deployer.create(_ABIMETHOD_OPTIONS, method="create", args=[governor, fee_asset]).client


def _params(method: str, *args: object) -> au.AppClientMethodCallParams:
    # a random note keeps otherwise-identical txns unique within the ledger
    return au.AppClientMethodCallParams(method=method, args=list(args), note=random.randbytes(8))


def _funded_account(deployer: Deployer) -> au.AddressWithSigners:
    """A second account (distinct from the deployer) that holds no assets."""
    other = deployer.localnet.account.random()
    deployer.localnet.account.ensure_funded(
        account_to_fund=other.addr,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_algo(1),
    )
    return other


# --- create="require" ---------------------------------------------------------


def test_create_initializes_governor_and_fee_asset(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    assert client.app_id


def test_bare_create_is_rejected(deployer: Deployer) -> None:
    # `create="require"` on `create` means a bare app create must fail
    with pytest.raises((au.LogicError, TransactionComposerError)):
        deployer.create_bare(_ABIMETHOD_OPTIONS)


# --- @public --------------------------------------------------------------------


def test_public_governor_getter_returns_governor(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    result = client.send.call(_params("public_governor_getter"))
    assert result.abi_return == account.addr


# --- name= ----------------------------------------------------------------------


def test_ping_uses_renamed_abi_method(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # `name="ping"` decouples the ABI name from the python name long_internal_name
    result = client.send.call(_params("ping"))
    assert result.abi_return == "ping"


# --- readonly= --------------------------------------------------------------------


def test_get_join_event_count_readonly(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    result = client.send.call(_params("get_join_event_count"))
    assert result.abi_return == 0


# --- default_args= ----------------------------------------------------------------


def test_admin_action_with_explicit_args(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # explicitly passing the values the defaults would resolve to
    result = client.send.call(_params("admin_action", asset_a, 0))
    assert result.confirmation.confirmed_round


def test_admin_action_defaults_resolved_by_client(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # passing None makes the client resolve each default from the ARC-56
    # metadata: fee_asset from global state, expected_join_event_count by
    # simulating the readonly get_join_event_count method
    result = client.send.call(_params("admin_action", None, None))
    assert result.confirmation.confirmed_round


def test_admin_action_rejects_non_governor(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    other = _funded_account(deployer)
    other_client = client.clone(default_sender=other.addr, default_signer=other.signer)
    # a non-governor sender is rejected even when passing the correct
    # state values for every argument (auth checks stored state, not args)
    with pytest.raises(au.LogicError, match="only governor"):
        other_client.send.call(_params("admin_action", asset_a, 0))


def test_admin_action_tolerates_wrong_fee_asset(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int, asset_b: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # a mismatched asset takes the early-return branch instead of failing —
    # even the stale count (999) is never checked, since the branch returns first
    result = client.send.call(_params("admin_action", asset_b, 999))
    assert result.confirmation.confirmed_round


def test_admin_action_rejects_stale_join_event_count(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    with pytest.raises(au.LogicError, match="stale join event count"):
        client.send.call(_params("admin_action", asset_a, 5))


# --- resource_encoding= -------------------------------------------------------------


def test_eligible_balance(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # the deployer account created asset_a (so holds it) and opts in to the app
    client.send.opt_in(_params("join"))
    result = client.send.call(_params("eligible_balance", asset_a, client.app_id, account.addr))
    assert isinstance(result.abi_return, int)
    assert result.abi_return > 0


def test_eligible_balance_requires_app_opt_in(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    # no opt-in to the app has happened
    with pytest.raises(au.LogicError, match="account not opted in to app"):
        client.send.call(_params("eligible_balance", asset_a, client.app_id, account.addr))


def test_eligible_balance_requires_asset_holding(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    localnet = deployer.localnet
    other = _funded_account(deployer)
    other_client = client.clone(default_sender=other.addr, default_signer=other.signer)

    # `other` opts in to the fee asset (with zero balance) so it can join the app
    localnet.send.asset_opt_in(au.AssetOptInParams(sender=other.addr, asset_id=asset_a))
    other_client.send.opt_in(_params("join"))
    # ...then opts back out of the asset, remaining opted in to the app only
    localnet.send.asset_opt_out(
        au.AssetOptOutParams(sender=other.addr, asset_id=asset_a, creator=account.addr)
    )

    with pytest.raises(au.LogicError, match="account is not opted in to the asset"):
        other_client.send.call(_params("eligible_balance", asset_a, client.app_id, other.addr))


# --- allow_actions= -----------------------------------------------------------------


def test_join_lifecycle_noop_optin_closeout(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)

    # NoOp join: allowed, but does not count as a new member
    client.send.call(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 0

    # OptIn join: allocates local state and increments the member count
    client.send.opt_in(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 1
    local_state = client.get_local_state(account.addr)
    joined_round = local_state["joined_round"].value
    assert isinstance(joined_round, int)
    assert joined_round > 0

    # NoOp join after opting in: still a member, count unchanged
    client.send.call(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 1

    # CloseOut via opt_out releases local state and counts the leave event;
    # the join event counter is never decremented
    client.send.close_out(_params("opt_out"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 1
    global_state = client.get_global_state()
    assert global_state["leave_event_count"].value == 1


def test_join_second_opt_in_rejected_by_network(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    client.send.opt_in(_params("join"))
    # an already-opted-in account cannot opt in again — the node rejects the
    # transaction before any contract logic runs, so `join_event_count` cannot be
    # inflated by repeating OptIn
    with pytest.raises(
        (au.LogicError, TransactionComposerError, ValueError), match="already opted in"
    ):
        client.send.opt_in(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 1


def test_join_event_count_drifts_after_clear_state(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    client.send.opt_in(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 1

    # ClearState wipes local state but cannot be blocked and bypasses the
    # CloseOut handler, so the leave is never recorded...
    client.send.bare.clear_state(au.AppClientBareCallParams(note=random.randbytes(8)))
    assert client.get_global_state()["leave_event_count"].value == 0

    # ...and rejoining records a second join event for the same account, so
    # join - leave now overcounts active members: the "best-effort" drift the
    # opt_out docstring warns about
    client.send.opt_in(_params("join"))
    assert client.send.call(_params("get_join_event_count")).abi_return == 2
    assert client.get_global_state()["leave_event_count"].value == 0


def test_join_requires_fee_asset(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    other = _funded_account(deployer)
    other_client = client.clone(default_sender=other.addr, default_signer=other.signer)
    # `other` is not opted in to the fee asset, so joining is rejected
    with pytest.raises(au.LogicError, match="must be opted in to fee asset"):
        other_client.send.opt_in(_params("join"))


def test_shut_down_only_governor(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _create(deployer, account.addr, asset_a)
    other = _funded_account(deployer)
    other_client = client.clone(default_sender=other.addr, default_signer=other.signer)

    with pytest.raises(au.LogicError, match="only governor can delete"):
        other_client.send.delete(_params("shut_down"))

    # the governor can delete the app
    result = client.send.delete(_params("shut_down"))
    assert result.confirmation.confirmed_round
