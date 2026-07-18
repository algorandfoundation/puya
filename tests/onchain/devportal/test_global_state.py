import random

import algokit_utils as au
import pytest
from algokit_common import public_key_from_address

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_GLOBAL_STATE = EXAMPLES_DIR / "devportal" / "global_state"


def _params(method: str, *args: object) -> au.AppClientMethodCallParams:
    # a random note keeps otherwise-identical txns unique within the ledger
    return au.AppClientMethodCallParams(method=method, args=list(args), note=random.randbytes(8))


def _storage(deployer: Deployer) -> au.AppClient:
    return deployer.create((_GLOBAL_STATE, "GlobalStorage")).client


def _storage_map(deployer: Deployer) -> au.AppClient:
    return deployer.create((_GLOBAL_STATE, "GlobalStorageMap")).client


# --- GlobalStorage --------------------------------------------------------


def test_get_global_state_default_when_empty(deployer: Deployer) -> None:
    client = _storage(deployer)
    # global_int_no_default starts empty -> .get(default=0) returns 0
    result = client.send.call(_params("get_global_state"))
    assert result.abi_return == 0


def test_maybe_global_state_when_empty(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("maybe_global_state"))
    # (value, exists): empty slot -> (0, False)
    assert result.abi_return == (0, False)


def test_get_global_state_example(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("get_global_state_example"))
    assert result.abi_return is True


def test_maybe_global_state_example(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("maybe_global_state_example"))
    assert result.abi_return is True


def test_check_global_state_example(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("check_global_state_example"))
    assert result.abi_return is True


def test_set_global_state(deployer: Deployer) -> None:
    client = _storage(deployer)
    client.send.call(_params("set_global_state", b"updated"))
    # global_bytes_full now holds the written value
    state = client.get_global_state()
    assert state["global_bytes_full"].value_raw == b"updated"


def test_set_global_state_example(deployer: Deployer, asset_a: int) -> None:
    client = _storage(deployer)
    value_bool = True
    client.send.call(
        # value_bytes, value_asset, value_app, value_account, value_bool
        _params(
            "set_global_state_example",
            b"world",
            asset_a,
            client.app_id,
            client.app_address,
            value_bool,
        )
    )
    state = client.get_global_state()
    assert state["global_bytes_no_default"].value_raw == b"world"
    assert state["global_int_simplified"].value == 99
    assert state["global_asset"].value == asset_a
    assert state["global_application"].value == client.app_id
    assert state["global_account"].value_raw == public_key_from_address(client.app_address)


def test_set_global_state_example_bool_false(deployer: Deployer, asset_a: int) -> None:
    client = _storage(deployer)
    value_bool = False
    # the method stores and verifies the written bool, so False also works
    client.send.call(
        _params(
            "set_global_state_example",
            b"world",
            asset_a,
            client.app_id,
            client.app_address,
            value_bool,
        )
    )
    state = client.get_global_state()
    assert state["global_bool_no_default"].value == 0


def test_del_global_state(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("del_global_state"))
    assert result.abi_return is True


def test_del_global_state_example(deployer: Deployer, asset_a: int) -> None:
    client = _storage(deployer)
    value_bool = True
    # populate the no_default slots first so deletion has something to remove
    client.send.call(
        _params(
            "set_global_state_example",
            b"world",
            asset_a,
            client.app_id,
            client.app_address,
            value_bool,
        )
    )
    result = client.send.call(_params("del_global_state_example"))
    assert result.abi_return is True


def test_del_global_state_example_when_empty(deployer: Deployer) -> None:
    client = _storage(deployer)
    # deleting global state keys that were never written still succeeds
    result = client.send.call(_params("del_global_state_example"))
    assert result.abi_return is True


def test_pass_proxy_to_subroutine(deployer: Deployer) -> None:
    client = _storage(deployer)
    # method sets global_int_no_default = 44, subroutine returns value + 1
    result = client.send.call(_params("pass_proxy_to_subroutine"))
    assert result.abi_return == 45


def test_dynamic_key_access(deployer: Deployer) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("dynamic_key_access"))
    # re-reads the same slots via dynamically constructed proxies
    assert result.abi_return == (7, b"hi")


# --- GlobalStorageMap -----------------------------------------------------


def test_global_map_set_and_get_score(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    client.send.call(_params("set_score", "alice", 42))
    result = client.send.call(_params("get_score", "alice"))
    assert result.abi_return == 42


def test_global_map_get_score_or_default(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    # missing key -> default 0
    missing = client.send.call(_params("get_score_or_default", "bob"))
    assert missing.abi_return == 0

    client.send.call(_params("set_score", "bob", 7))
    present = client.send.call(_params("get_score_or_default", "bob"))
    assert present.abi_return == 7


def test_global_map_maybe_score(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    absent = client.send.call(_params("maybe_score", "carol"))
    assert absent.abi_return == (0, False)

    client.send.call(_params("set_score", "carol", 9))
    present = client.send.call(_params("maybe_score", "carol"))
    assert present.abi_return == (9, True)


def test_global_map_get_missing_score_fails(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    # indexing a missing key fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_score", "nobody"))


def test_global_map_delete_score(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    client.send.call(_params("set_score", "dave", 5))
    client.send.call(_params("delete_score", "dave"))
    result = client.send.call(_params("maybe_score", "dave"))
    assert result.abi_return == (0, False)


def test_global_map_profiles(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    absent = client.send.call(_params("has_profile", 1))
    assert absent.abi_return is False

    client.send.call(_params("set_profile", 1, ("alice", 100)))
    present = client.send.call(_params("has_profile", 1))
    assert present.abi_return is True


def test_global_map_get_slot_proxy(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    client.send.call(_params("set_score", "eve", 88))
    result = client.send.call(_params("get_slot_proxy", "eve"))
    assert result.abi_return == 88


def test_global_map_get_slot_proxy_missing_key_fails(deployer: Deployer) -> None:
    client = _storage_map(deployer)
    # `.value` on the proxy of a missing key fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_slot_proxy", "nobody"))
