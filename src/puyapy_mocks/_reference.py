from __future__ import annotations

from puyapy_mocks import Bytes, UInt64
from puyapy_mocks._ctx_state import active_ctx


class Account:
    def __init__(self, address: str):
        self.address = address

    def __eq__(self, other: Account | str) -> bool:  # type: ignore[override]
        return True

    def __ne__(self, other: Account | str) -> bool:  # type: ignore[override]
        return True

    def __bool__(self) -> bool:
        return True

    @property
    def balance(self) -> UInt64:
        return UInt64(active_ctx().get_balance(self.address, 0))

    @property
    def min_balance(self) -> UInt64:
        return UInt64(0)

    @property
    def auth_address(self) -> Account:
        return self

    @property
    def total_num_uint(self) -> UInt64:
        return UInt64(0)

    @property
    def total_num_byte_slice(self) -> Bytes:
        return Bytes(b"")

    @property
    def total_extra_app_pages(self) -> UInt64:
        return UInt64(0)

    @property
    def total_apps_created(self) -> UInt64:
        return UInt64(0)

    @property
    def total_apps_opted_in(self) -> UInt64:
        return UInt64(0)

    @property
    def total_assets_created(self) -> UInt64:
        return UInt64(0)

    @property
    def total_assets(self) -> UInt64:
        return UInt64(0)

    @property
    def total_boxes(self) -> UInt64:
        return UInt64(0)

    @property
    def total_box_bytes(self) -> UInt64:
        return UInt64(0)


class Asset:
    def __init__(self, asset_id: UInt64 | int):
        self.asset_id = int(asset_id)

    @property
    def id(self) -> UInt64:
        return UInt64(self.asset_id)
