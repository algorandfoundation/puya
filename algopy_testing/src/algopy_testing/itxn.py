from __future__ import annotations

import typing
from copy import deepcopy
from typing import TYPE_CHECKING, TypedDict

from algopy_testing.context import get_test_context

if TYPE_CHECKING:

    import algopy

    from algopy_testing.enums import OnCompleteAction
    from algopy_testing.primitives.uint64 import UInt64


__all__ = [
    "BaseInnerTransaction",
    "InnerTransaction",
    "Payment",
    "KeyRegistration",
    "AssetConfig",
    "AssetTransfer",
    "AssetFreeze",
    "ApplicationCall",
]


class BaseInnerTransaction:
    def submit(self) -> object:
        context = get_test_context()

        if not context:
            raise RuntimeError("No test context found")

        context.add_inner_transaction(self)
        # TODO: consider additional fields that are populated by AVM after submission such
        #       as TxID
        # TODO: add wrapper around result that converts co-variant types to invariant types
        #       e.g. algopy.UInt64 | int -> algopy.UInt64
        return self

    def copy(self) -> typing.Self:
        return deepcopy(self)

    # ideally the type dict used for each field would be a type parameter of this class
    # unfortunately type dicts aren't true types, so can't be used as such
    def _get_fields(self) -> dict[str, typing.Any]:
        fields = self.fields  # type: ignore[attr-defined]
        return typing.cast(dict[str, typing.Any], fields)

    def get_field(self, type_dict: object, name: str) -> object:
        if name in type_dict.__annotations__:
            return self._get_fields().get(name)

        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseInnerTransaction):
            return bool(self._get_fields() == other._get_fields())
        return False

    def __hash__(self) -> int:
        return hash(self._get_fields())


class InnerTransactionFields(TypedDict, total=False):
    type: algopy.TransactionType
    receiver: algopy.Account | str
    amount: algopy.UInt64 | int
    close_remainder_to: algopy.Account | str
    vote_key: algopy.Bytes | bytes
    selection_key: algopy.Bytes | bytes
    vote_first: algopy.UInt64 | int
    vote_last: algopy.UInt64 | int
    vote_key_dilution: algopy.UInt64 | int
    non_participation: algopy.UInt64 | int | bool
    state_proof_key: algopy.Bytes | bytes
    config_asset: algopy.Asset | algopy.UInt64 | int
    total: UInt64 | int
    unit_name: algopy.String | algopy.Bytes | str | bytes
    asset_name: algopy.String | algopy.Bytes | str | bytes
    decimals: algopy.UInt64 | int
    default_frozen: bool
    url: algopy.String | algopy.Bytes | bytes | str
    metadata_hash: algopy.Bytes | bytes
    manager: algopy.Account | str
    reserve: algopy.Account | str
    freeze: algopy.Account | str
    clawback: algopy.Account | str
    xfer_asset: algopy.Asset | algopy.UInt64 | int
    asset_amount: algopy.UInt64 | int
    asset_sender: algopy.Account | str
    asset_receiver: algopy.Account | str
    asset_close_to: algopy.Account | str
    freeze_asset: algopy.Asset | algopy.UInt64 | int
    freeze_account: algopy.Account | str
    frozen: bool
    app_id: algopy.Application | algopy.UInt64 | int
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    on_completion: OnCompleteAction | algopy.UInt64 | int
    global_num_uint: algopy.UInt64 | int
    global_num_bytes: algopy.UInt64 | int
    local_num_uint: algopy.UInt64 | int
    local_num_bytes: algopy.UInt64 | int
    extra_program_pages: algopy.UInt64 | int
    app_args: tuple[algopy.Bytes, ...]
    accounts: tuple[algopy.Account, ...]
    assets: tuple[algopy.Asset, ...]
    apps: tuple[algopy.Application, ...]
    sender: algopy.Account
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class InnerTransaction(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[InnerTransactionFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[InnerTransactionFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(InnerTransactionFields, name)


class PaymentFields(TypedDict, total=False):
    receiver: algopy.Account
    amount: algopy.UInt64
    close_remainder_to: algopy.Account
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class Payment(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[PaymentFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[PaymentFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(PaymentFields, name)


class KeyRegistrationFields(TypedDict, total=False):
    vote_key: algopy.Bytes
    selection_key: algopy.Bytes
    vote_first: algopy.UInt64
    vote_last: algopy.UInt64
    vote_key_dilution: algopy.UInt64
    non_participation: algopy.UInt64
    state_proof_key: algopy.Bytes
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class KeyRegistration(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[KeyRegistrationFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[KeyRegistrationFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(KeyRegistrationFields, name)


class AssetConfigFields(TypedDict, total=False):
    config_asset: algopy.Asset
    total: algopy.UInt64
    unit_name: algopy.String
    asset_name: algopy.String
    decimals: algopy.UInt64
    default_frozen: bool
    url: algopy.String
    metadata_hash: algopy.Bytes
    manager: algopy.Account
    reserve: algopy.Account
    freeze: algopy.Account
    clawback: algopy.Account
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class AssetConfig(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[AssetConfigFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[AssetConfigFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetConfigFields, name)


class AssetTransferFields(TypedDict, total=False):
    xfer_asset: algopy.Asset
    asset_amount: algopy.UInt64
    asset_sender: algopy.Account
    asset_receiver: algopy.Account
    asset_close_to: algopy.Account
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class AssetTransfer(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[AssetTransferFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[AssetTransferFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetTransferFields, name)


class AssetFreezeFields(TypedDict, total=False):
    freeze_asset: algopy.Asset
    freeze_account: algopy.Account
    frozen: bool
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class AssetFreeze(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[AssetFreezeFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[AssetFreezeFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetFreezeFields, name)


class ApplicationCallFields(TypedDict, total=False):
    app_id: algopy.Application
    approval_program: algopy.Bytes
    clear_state_program: algopy.Bytes
    on_completion: algopy.OnCompleteAction
    global_num_uint: algopy.UInt64
    global_num_bytes: algopy.UInt64
    local_num_uint: algopy.UInt64
    local_num_bytes: algopy.UInt64
    extra_program_pages: algopy.UInt64
    app_args: list[algopy.Bytes | algopy.String | algopy.BigUInt]
    accounts: list[algopy.Account]
    assets: list[algopy.Asset]
    apps: list[algopy.Application]
    sender: algopy.Account
    fee: algopy.UInt64
    note: algopy.String
    rekey_to: algopy.Account


class ApplicationCall(BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[ApplicationCallFields]):
        self.fields = kwargs

    def set(self, **kwargs: typing.Unpack[ApplicationCallFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(InnerTransactionFields, name)
