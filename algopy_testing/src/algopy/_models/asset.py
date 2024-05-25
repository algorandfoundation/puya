from __future__ import annotations

from typing import TypedDict, TypeVar, cast
from unittest.mock import MagicMock

from algopy._models import Account
from algopy._primitives import Bytes, UInt64
from algopy.utils import as_string


class AssetOverrides(TypedDict, total=False):
    total: UInt64
    decimals: UInt64
    default_frozen: bool
    unit_name: Bytes
    name: Bytes
    url: Bytes
    metadata_hash: Bytes
    manager: Account
    reserve: Account
    freeze: Account
    clawback: Account
    creator: Account


T = TypeVar("T")


class Asset:
    _asset_id: UInt64

    def __init__(self, asset_id: UInt64 | int = 0, /, **overrides: AssetOverrides):
        if not isinstance(asset_id, UInt64 | int):
            raise TypeError("Invalid value for Asset ID")
        self._asset_id = asset_id if isinstance(asset_id, UInt64) else UInt64(asset_id)
        self._overrides = overrides

    def __eq__(self, other: object) -> bool:
        return self._asset_id == as_string(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self._asset_id != 0

    @property
    def id(self) -> UInt64:
        return self._asset_id

    def _get_property(self, name: str, default: T) -> T:
        return cast(T, self._overrides.get(name, default))

    @property
    def total(self) -> UInt64:
        return self._get_property("total", MagicMock(spec=UInt64))

    @property
    def decimals(self) -> UInt64:
        return self._get_property("decimals", MagicMock(spec=UInt64))

    @property
    def default_frozen(self) -> bool:
        return self._get_property("default_frozen", MagicMock(spec=bool))

    @property
    def unit_name(self) -> Bytes:
        return self._get_property("unit_name", MagicMock(spec=Bytes))

    @property
    def name(self) -> Bytes:
        return self._get_property("name", MagicMock(spec=Bytes))

    @property
    def url(self) -> Bytes:
        return self._get_property("url", MagicMock(spec=Bytes))

    @property
    def metadata_hash(self) -> Bytes:
        return self._get_property("metadata_hash", MagicMock(spec=Bytes))

    @property
    def manager(self) -> Account:
        return self._get_property("manager", MagicMock(spec=Account))

    @property
    def reserve(self) -> Account:
        return self._get_property("reserve", MagicMock(spec=Account))

    @property
    def freeze(self) -> Account:
        return self._get_property("freeze", MagicMock(spec=Account))

    @property
    def clawback(self) -> Account:
        return self._get_property("clawback", MagicMock(spec=Account))

    @property
    def creator(self) -> Account:
        return self._get_property("creator", MagicMock(spec=Account))

    def balance(self, _account: Account, /) -> UInt64:
        raise NotImplementedError(
            "The 'balance' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )

    def frozen(self, _account: Account, /) -> bool:
        raise NotImplementedError(
            "The 'frozen' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )
