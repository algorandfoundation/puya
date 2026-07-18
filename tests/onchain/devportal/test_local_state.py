import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_LOCAL_STATE = EXAMPLES_DIR / "devportal" / "local_state"


def _params(method: str, *args: object) -> au.AppClientMethodCallParams:
    # a random note keeps otherwise-identical txns unique within the ledger
    return au.AppClientMethodCallParams(method=method, args=list(args), note=random.randbytes(8))


def _storage(deployer: Deployer) -> au.AppClient:
    """Deploy LocalStorage and opt the sender account in."""
    client = deployer.create((_LOCAL_STATE, "LocalStorage")).client
    client.send.opt_in(_params("opt_in"))
    return client


def _storage_map(deployer: Deployer) -> au.AppClient:
    """Deploy LocalStorageMap and opt the sender account in."""
    client = deployer.create((_LOCAL_STATE, "LocalStorageMap")).client
    client.send.opt_in(_params("opt_in"))
    return client


# --- LocalStorage ---------------------------------------------------------


def test_contains_local_data(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    # opt_in wrote local_int for the sender
    result = client.send.call(_params("contains_local_data", account.addr))
    assert result.abi_return is True


def test_contains_local_data_example(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("contains_local_data_example", account.addr))
    assert result.abi_return is True


def test_get_item_local_data(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    # opt_in set local_int = 10
    result = client.send.call(_params("get_item_local_data", account.addr))
    assert result.abi_return == 10


def test_get_item_local_data_example(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("get_item_local_data_example", account.addr))
    assert result.abi_return is True


def test_get_local_data_with_default(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("get_local_data_with_default", account.addr))
    assert result.abi_return is True


def test_get_local_data_with_default_int_when_absent(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    # opt_in sets local_int=10; delete it so the slot is absent for an
    # opted-in account, then `.get(default=0)` returns the default 0
    client = _storage(deployer)
    client.send.call(_params("delete_local_data", account.addr))
    result = client.send.call(_params("get_local_data_with_default_int", account.addr))
    assert result.abi_return == 0


def test_maybe_local_data(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("maybe_local_data", account.addr))
    assert result.abi_return == (10, True)


def test_maybe_local_data_example(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("maybe_local_data_example", account.addr))
    assert result.abi_return is True


def test_set_local_int(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    client.send.call(_params("set_local_int", account.addr, 123))
    result = client.send.call(_params("get_item_local_data", account.addr))
    assert result.abi_return == 123


def test_set_local_data_example(
    deployer: Deployer, account: au.AddressWithSigners, asset_a: int
) -> None:
    client = _storage(deployer)
    value_bool = True
    result = client.send.call(
        # for_account, value_asset, value_account, value_app, value_bytes, value_bool
        _params(
            "set_local_data_example",
            account.addr,
            asset_a,
            account.addr,
            client.app_id,
            b"data",
            value_bool,
        )
    )
    assert result.abi_return is True


def test_delete_local_data(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    client.send.call(_params("delete_local_data", account.addr))
    contains = client.send.call(_params("contains_local_data", account.addr))
    assert contains.abi_return is False


def test_delete_local_data_example(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    result = client.send.call(_params("delete_local_data_example", account.addr))
    assert result.abi_return is True


def test_pass_proxy_to_subroutine(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage(deployer)
    # local_int is 10, subroutine returns value + 1
    result = client.send.call(_params("pass_proxy_to_subroutine", account.addr))
    assert result.abi_return == 11


def test_get_item_local_data_missing_account_fails(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    # on a fresh app the account has not opted in, so indexing local_int fails
    client = deployer.create((_LOCAL_STATE, "LocalStorage")).client
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_item_local_data", account.addr))


def test_set_local_int_not_opted_in_fails(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    # writing local state also requires the account to be opted in
    client = deployer.create((_LOCAL_STATE, "LocalStorage")).client
    with pytest.raises(au.LogicError):
        client.send.call(_params("set_local_int", account.addr, 123))


# --- LocalStorageMap ------------------------------------------------------


def test_local_map_get_balance(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    # opt_in set balances[(sender, "USD")] = 100
    result = client.send.call(_params("get_balance", account.addr, "USD"))
    assert result.abi_return == 100


def test_local_map_get_balance_missing_key_fails(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _storage_map(deployer)
    # indexing a (account, key) pair with no stored value fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_balance", account.addr, "EUR"))


def test_local_map_get_balance_or_default(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _storage_map(deployer)
    # "EUR" was never set -> default 0
    missing = client.send.call(_params("get_balance_or_default", account.addr, "EUR"))
    assert missing.abi_return == 0
    present = client.send.call(_params("get_balance_or_default", account.addr, "USD"))
    assert present.abi_return == 100


def test_local_map_maybe_balance(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    absent = client.send.call(_params("maybe_balance", account.addr, "GBP"))
    assert absent.abi_return == (0, False)
    present = client.send.call(_params("maybe_balance", account.addr, "USD"))
    assert present.abi_return == (100, True)


def test_local_map_has_flag(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    # opt_in set flags[(sender, 0)] = True
    has = client.send.call(_params("has_flag", account.addr, 0))
    assert has.abi_return is True
    missing = client.send.call(_params("has_flag", account.addr, 99))
    assert missing.abi_return is False


def test_local_map_set_balance(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    client.send.call(_params("set_balance", account.addr, "USD", 500))
    result = client.send.call(_params("get_balance", account.addr, "USD"))
    assert result.abi_return == 500


def test_local_map_set_flag(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    flag_value = True
    client.send.call(_params("set_flag", account.addr, 7, flag_value))
    result = client.send.call(_params("has_flag", account.addr, 7))
    assert result.abi_return is True


def test_local_map_set_flag_false_still_exists(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _storage_map(deployer)
    flag_value = False
    client.send.call(_params("set_flag", account.addr, 8, flag_value))
    # `in` reports key existence regardless of the truthiness of the value
    result = client.send.call(_params("has_flag", account.addr, 8))
    assert result.abi_return is True


def test_local_map_delete_balance(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    client.send.call(_params("delete_balance", account.addr, "USD"))
    result = client.send.call(_params("maybe_balance", account.addr, "USD"))
    assert result.abi_return == (0, False)


def test_local_map_get_slot_proxy(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _storage_map(deployer)
    result = client.send.call(_params("get_slot_proxy", account.addr, "USD"))
    assert result.abi_return == 100
