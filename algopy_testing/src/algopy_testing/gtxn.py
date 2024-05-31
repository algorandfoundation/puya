from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import algopy


@dataclass
class _GroupTransaction:
    group_index: algopy.UInt64 | int = field(default=0)

    def __init__(self, group_index: algopy.UInt64 | int) -> None:
        self.group_index = group_index


@dataclass
class TransactionBase(_GroupTransaction):
    sender: algopy.Account | None = field(default=None)
    fee: algopy.UInt64 | None = field(default=None)
    first_valid: algopy.UInt64 | None = field(default=None)
    first_valid_time: algopy.UInt64 | None = field(default=None)
    last_valid: algopy.UInt64 | None = field(default=None)
    note: algopy.Bytes | None = field(default=None)
    lease: algopy.Bytes | None = field(default=None)
    type_bytes: algopy.Bytes | None = field(default=None)
    type: algopy.TransactionType | None = field(default=None)
    txn_id: algopy.Bytes | None = field(default=None)
    rekey_to: algopy.Account | None = field(default=None)


@dataclass
class AssetTransferTransaction(TransactionBase):
    xfer_asset: algopy.Asset | None = field(default=None)
    asset_amount: algopy.UInt64 | None = field(default=None)
    asset_sender: algopy.Account | None = field(default=None)
    asset_receiver: algopy.Account | None = field(default=None)
    asset_close_to: algopy.Account | None = field(default=None)


@dataclass
class PaymentTransaction(TransactionBase):
    receiver: algopy.Account | None = field(default=None)
    amount: algopy.UInt64 | None = field(default=None)
    close_remainder_to: algopy.Account | None = field(default=None)
