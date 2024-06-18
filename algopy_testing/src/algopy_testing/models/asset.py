from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, TypeVar

if TYPE_CHECKING:
    import algopy


T = TypeVar("T")


class AssetFields(TypedDict, total=False):
    total: algopy.UInt64
    decimals: algopy.UInt64
    default_frozen: bool
    unit_name: algopy.Bytes
    name: algopy.Bytes
    url: algopy.Bytes
    metadata_hash: algopy.Bytes
    manager: algopy.Account
    reserve: algopy.Account
    freeze: algopy.Account
    clawback: algopy.Account
    creator: algopy.Account


@dataclass
class Asset:
    id: algopy.UInt64

    def __init__(self, asset_id: algopy.UInt64 | int = 0):
        from algopy import UInt64

        self.id = asset_id if isinstance(asset_id, UInt64) else UInt64(asset_id)

    def balance(self, account: algopy.Account) -> algopy.UInt64:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )

        if account not in context._account_data:
            raise ValueError(
                "The account is not present in the test context! "
                "Use `context.add_account()` or `context.any_account()` to add the account to "
                "your test setup."
            )

        account_data = context._account_data.get(str(account), None)

        if not account_data:
            raise ValueError("Account not found in testing context!")

        if int(self.id) not in account_data.opted_asset_balances:
            raise ValueError(
                "The asset is not opted into the account! "
                "Use `account.opt_in()` to opt the asset into the account."
            )

        return account_data.opted_asset_balances[self.id]

    def frozen(self, _account: algopy.Account) -> bool:
        raise NotImplementedError(
            "The 'frozen' method is being executed in a python testing context. "
            "Please mock this method using your python testing framework of choice."
        )

    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )

        if int(self.id) not in context._asset_data:
            raise ValueError(
                "`algopy.Asset` is not present in the test context! "
                "Use `context.add_asset()` or `context.any_asset()` to add the asset to "
                "your test setup."
            )

        return_value = context._asset_data[int(self.id)].get(name)
        if return_value is None:
            raise AttributeError(
                f"The value for '{name}' in the test context is None. "
                f"Make sure to patch the global field '{name}' using your `AlgopyTestContext` "
                "instance."
            )

        return return_value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Asset):
            return self.id == other.id
        return self.id == other

    def __bool__(self) -> bool:
        return self.id != 0

    def __hash__(self) -> int:
        return hash(self.id)
