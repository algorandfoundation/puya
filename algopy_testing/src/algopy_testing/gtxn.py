from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict, get_type_hints

if TYPE_CHECKING:
    import algopy


@dataclass
class _GroupTransaction:
    group_index: algopy.UInt64 | int = field(default=0)

    def __init__(self, group_index: algopy.UInt64 | int) -> None:
        self.group_index = group_index


class TransactionBaseFields(TypedDict, total=False):
    sender: algopy.Account
    fee: algopy.UInt64
    first_valid: algopy.UInt64
    first_valid_time: algopy.UInt64
    last_valid: algopy.UInt64
    note: algopy.Bytes
    lease: algopy.Bytes
    type_bytes: algopy.Bytes
    type: algopy.TransactionType
    txn_id: algopy.Bytes
    rekey_to: algopy.Account


@dataclass
class TransactionBase(_GroupTransaction):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[TransactionBaseFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def set(self, **kwargs: typing.Unpack[TransactionBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> object:
        type_hints = get_type_hints(TransactionBaseFields)

        if name in type_hints:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class AssetTransferFields(TransactionBaseFields, total=False):
    xfer_asset: algopy.Asset
    asset_amount: algopy.UInt64
    asset_sender: algopy.Account
    asset_receiver: algopy.Account
    asset_close_to: algopy.Account


@dataclass
class AssetTransferTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[AssetTransferFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def set(self, **kwargs: typing.Unpack[AssetTransferFields]) -> None:
        """Updates inner transaction parameter values"""
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> object:
        type_hints = get_type_hints(AssetTransferFields)

        if name in type_hints:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class PaymentFields(TransactionBaseFields, total=False):
    receiver: algopy.Account
    amount: algopy.UInt64
    close_remainder_to: algopy.Account


@dataclass
class PaymentTransaction(TransactionBase):
    def __init__(self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[PaymentFields]):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def set(self, **kwargs: typing.Unpack[PaymentFields]) -> None:
        """Updates inner transaction parameter values"""
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> object:
        type_hints = get_type_hints(PaymentFields)

        if name in type_hints:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# TODO: Implement remaining transaction types
@dataclass
class ApplicationCallTransaction(TransactionBase):
    pass


@dataclass
class KeyRegistrationTransaction(TransactionBase):
    pass


@dataclass
class AssetConfigTransaction(TransactionBase):
    pass


@dataclass
class AssetFreezeTransaction(TransactionBase):
    pass


@dataclass
class Transaction(TransactionBase):
    pass


__all__ = [
    "TransactionBase",
    "AssetTransferTransaction",
    "PaymentTransaction",
    "ApplicationCallTransaction",
    "KeyRegistrationTransaction",
    "AssetConfigTransaction",
    "AssetFreezeTransaction",
    "Transaction",
]
