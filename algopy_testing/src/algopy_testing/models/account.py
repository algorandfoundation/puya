from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, TypedDict, TypeVar

import algosdk

from algopy_testing.primitives.bytes import Bytes
from algopy_testing.utils import as_string

if TYPE_CHECKING:
    import algopy


T = TypeVar("T")


class AccountFields(TypedDict, total=False):
    balance: algopy.UInt64
    min_balance: algopy.UInt64
    auth_address: algopy.Account
    total_num_uint: algopy.UInt64
    total_num_byte_slice: algopy.Bytes
    total_extra_app_pages: algopy.UInt64
    total_apps_created: algopy.UInt64
    total_apps_opted_in: algopy.UInt64
    total_assets_created: algopy.UInt64
    total_assets: algopy.UInt64
    total_boxes: algopy.UInt64
    total_box_bytes: algopy.UInt64


@dataclass()
class Account:
    _public_key: str

    def __init__(self, value: str | Bytes = algosdk.constants.ZERO_ADDRESS, /):
        if not isinstance(value, (str | Bytes)):
            raise TypeError("Invalid value for Account")
        if isinstance(value, Bytes):
            public_key = algosdk.encoding.encode_address(value)
        else:
            public_key = value
        self._public_key = public_key

    def is_opted_in(self, asset_or_app: algopy.Asset | algopy.Application, /) -> bool:
        from algopy import Application, Asset

        from algopy_testing import get_test_context

        context = get_test_context()
        opted_apps = context.account_data[self._public_key].opted_apps
        opted_asset_balances = context.account_data[self._public_key].opted_asset_balances

        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )

        if isinstance(asset_or_app, Asset):
            return asset_or_app.id in opted_asset_balances
        elif isinstance(asset_or_app, Application):
            return asset_or_app.id in opted_apps

        raise TypeError(
            "Invalid `asset_or_app` argument type. Must be an `algopy.Asset` or "
            "`algopy.Application` instance."
        )

    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes) -> Self:
        from algopy import Bytes

        if not isinstance(value, (Bytes | bytes)):
            raise TypeError("Invalid value for Account")

        value_len = value.length if isinstance(value, Bytes) else len(value)
        if value_len != 32:
            raise ValueError(
                f"Invalid account value byte length: {value_len} bytes; must be 32 bytes long."
            )
        if isinstance(value, bytes):
            decoded_value = algosdk.encoding.encode_address(value)
        else:
            decoded_value = str(value)
        return cls(decoded_value)

    @property
    def bytes(self) -> Bytes:
        return Bytes(algosdk.encoding.decode_address(self._public_key)[:32])

    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if self._public_key not in context.account_data:
            raise ValueError(
                "`algopy.Account` is not present in the test context! "
                "Use `context.add_account()` or `context.any_account()` to add the account "
                "to your test setup."
            )

        return_value = context.account_data[self._public_key].data.get(name)
        if return_value is None:
            raise TypeError(
                f"The value for '{name}' in the test context is None. "
                f"Make sure to patch the global field '{name}' using your `AlgopyTestContext` "
                "instance."
            )

        return return_value

    def __repr__(self) -> str:
        return self._public_key

    def __str__(self) -> str:
        return self._public_key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Account | str):
            raise TypeError("Invalid value for Account")
        if isinstance(other, Account):
            return self._public_key == other._public_key
        return self._public_key == as_string(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self._public_key != algosdk.constants.ZERO_ADDRESS

    def __hash__(self) -> int:
        return hash(self._public_key)


@dataclass
class AccountData:
    """
    Data class to store account-related information.

    Attributes:
        opted_asset_balances (dict[int, algopy.UInt64]): A dictionary mapping asset IDs to their
        balances.
        opted_app_ids (dict[int, algopy.UInt64]): A dictionary mapping application IDs to
        their instances.
        data (AccountFields): Additional account fields.
    """

    opted_asset_balances: dict[algopy.UInt64, algopy.UInt64]
    opted_apps: dict[algopy.UInt64, algopy.Application]
    data: AccountFields
