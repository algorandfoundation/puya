from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

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
        if name in TransactionBaseFields.__annotations__:
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

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in AssetTransferFields.__annotations__:
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

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in PaymentFields.__annotations__:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class ApplicationCallFields(TransactionBaseFields, total=False):
    app_id: algopy.Application
    on_completion: algopy.OnCompleteAction
    num_app_args: algopy.UInt64
    num_accounts: algopy.UInt64
    approval_program: algopy.Bytes
    clear_state_program: algopy.Bytes
    num_assets: algopy.UInt64
    num_apps: algopy.UInt64
    global_num_uint: algopy.UInt64
    global_num_bytes: algopy.UInt64
    local_num_uint: algopy.UInt64
    local_num_bytes: algopy.UInt64
    extra_program_pages: algopy.UInt64
    last_log: algopy.Bytes
    num_approval_program_pages: algopy.UInt64
    num_clear_state_program_pages: algopy.UInt64

    app_args: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]
    accounts: typing.Callable[[algopy.UInt64 | int], algopy.Account]
    assets: typing.Callable[[algopy.UInt64 | int], algopy.Asset]
    apps: typing.Callable[[algopy.UInt64 | int], algopy.Application]
    approval_program_pages: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]
    clear_state_program_pages: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]


@dataclass
class ApplicationCallTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[ApplicationCallFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in ApplicationCallFields.__annotations__:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class KeyRegistrationFields(TransactionBaseFields, total=False):
    vote_key: algopy.Bytes
    selection_key: algopy.Bytes
    vote_first: algopy.UInt64
    vote_last: algopy.UInt64
    vote_key_dilution: algopy.UInt64
    non_participation: bool
    state_proof_key: algopy.Bytes


class KeyRegistrationTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[KeyRegistrationFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in KeyRegistrationFields.__annotations__:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class AssetConfigFields(TransactionBaseFields, total=False):
    config_asset: algopy.Asset
    total: algopy.UInt64
    decimals: algopy.UInt64
    default_frozen: bool
    unit_name: algopy.Bytes
    asset_name: algopy.Bytes
    url: algopy.Bytes
    metadata_hash: algopy.Bytes
    manager: algopy.Account
    reserve: algopy.Account
    freeze: algopy.Account
    clawback: algopy.Account


@dataclass
class AssetConfigTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[AssetConfigFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in AssetConfigFields.__annotations__:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class AssetFreezeFields(TransactionBaseFields, total=False):
    freeze_asset: algopy.Asset
    freeze_account: algopy.Account
    frozen: bool


@dataclass
class AssetFreezeTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[AssetFreezeFields]
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in AssetFreezeFields.__annotations__:
            return self.__dict__.get(name)

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


@dataclass
class Transaction(TransactionBase):
    def __init__(
        self,
        group_index: algopy.UInt64 | int,
        **kwargs: dict[str, typing.Any],
    ):
        super().__init__(group_index=group_index)
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:  # noqa: ANN401
        if name in {
            **TransactionBaseFields.__annotations__,
            **AssetTransferFields.__annotations__,
            **PaymentFields.__annotations__,
            **ApplicationCallFields.__annotations__,
            **KeyRegistrationFields.__annotations__,
            **AssetConfigFields.__annotations__,
            **AssetFreezeFields.__annotations__,
        }:
            return self.__dict__[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


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
