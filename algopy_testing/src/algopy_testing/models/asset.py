from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from algopy_testing.models.account import Account
    from algopy_testing.primitives.bytes import Bytes
    from algopy_testing.primitives.uint64 import UInt64

T = TypeVar("T")


@dataclass
class Asset:
    id: UInt64 | None = None
    total: UInt64 | None = None
    decimals: UInt64 | None = None
    default_frozen: bool | None = None
    unit_name: Bytes | None = None
    name: Bytes | None = None
    url: Bytes | None = None
    metadata_hash: Bytes | None = None
    manager: Account | None = None
    reserve: Account | None = None
    freeze: Account | None = None
    clawback: Account | None = None
    creator: Account | None = None

    def __init__(self, asset_id: UInt64 | int = 0, /):
        from algopy_testing.primitives.uint64 import UInt64

        self.id = asset_id if isinstance(asset_id, UInt64) else UInt64(asset_id)

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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Asset):
            return self.id == other.id
        return self.id == other

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    # truthiness
    def __bool__(self) -> bool:
        return self.id != 0
