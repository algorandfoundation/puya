from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, TypeVar, cast
from unittest.mock import MagicMock

import algosdk

from algopy._primitives.bytes import Bytes
from algopy._primitives.uint64 import UInt64
from algopy.utils import as_string

if TYPE_CHECKING:
    from algopy._models.application import Application
    from algopy._models.asset import Asset


class AccountOverrides(TypedDict, total=False):
    balance: UInt64
    min_balance: UInt64
    auth_address: Account
    total_num_uint: UInt64
    total_num_byte_slice: Bytes
    total_extra_app_pages: UInt64
    total_apps_created: UInt64
    total_apps_opted_in: UInt64
    total_assets_created: UInt64
    total_assets: UInt64
    total_boxes: UInt64
    total_box_bytes: UInt64


T = TypeVar("T")


class Account:
    _public_key: str

    def __init__(
        self, value: str | Bytes = algosdk.constants.ZERO_ADDRESS, /, **overrides: AccountOverrides
    ):
        if not isinstance(value, str | Bytes):
            raise TypeError("Invalid value for Account")
        self._public_key = as_string(value)
        self._overrides = overrides

    def __eq__(self, other: object) -> bool:
        return self._public_key == as_string(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self._public_key != algosdk.constants.ZERO_ADDRESS

    def _get_property(self, name: str, default: T) -> T:
        return cast(T, self._overrides.get(name, default))

    @property
    def balance(self) -> UInt64:
        return self._get_property("balance", MagicMock(spec=UInt64))

    @property
    def min_balance(self) -> UInt64:
        return self._get_property("min_balance", MagicMock(spec=UInt64))

    @property
    def auth_address(self) -> Account:
        return self._get_property("auth_address", MagicMock(spec=Account))

    @property
    def total_num_uint(self) -> UInt64:
        return self._get_property("total_num_uint", MagicMock(spec=UInt64))

    @property
    def total_num_byte_slice(self) -> Bytes:
        return self._get_property("total_num_byte_slice", MagicMock(spec=Bytes))

    @property
    def total_extra_app_pages(self) -> UInt64:
        return self._get_property("total_extra_app_pages", MagicMock(spec=UInt64))

    @property
    def total_apps_created(self) -> UInt64:
        return self._get_property("total_apps_created", MagicMock(spec=UInt64))

    @property
    def total_apps_opted_in(self) -> UInt64:
        return self._get_property("total_apps_opted_in", MagicMock(spec=UInt64))

    @property
    def total_assets_created(self) -> UInt64:
        return self._get_property("total_assets_created", MagicMock(spec=UInt64))

    @property
    def total_assets(self) -> UInt64:
        return self._get_property("total_assets", MagicMock(spec=UInt64))

    @property
    def total_boxes(self) -> UInt64:
        return self._get_property("total_boxes", MagicMock(spec=UInt64))

    @property
    def total_box_bytes(self) -> UInt64:
        return self._get_property("total_box_bytes", MagicMock(spec=UInt64))

    def is_opted_in(self, asset_or_app: Asset | Application, /) -> bool:
        raise NotImplementedError(
            "The 'is_opted_in' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )

    @classmethod
    def from_bytes(cls, value: Bytes | bytes) -> Account:
        return cls(as_string(value))

    @property
    def bytes(self) -> Bytes:
        return Bytes(self._public_key.encode("utf-8"))
