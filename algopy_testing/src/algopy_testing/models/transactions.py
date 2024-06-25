from __future__ import annotations

import typing
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import algopy


class _TransactionCoreFields(TypedDict, total=False):
    sender: algopy.Account
    fee: algopy.UInt64
    first_valid: algopy.UInt64
    first_valid_time: algopy.UInt64
    last_valid: algopy.UInt64
    note: algopy.Bytes
    lease: algopy.Bytes
    txn_id: algopy.Bytes
    rekey_to: algopy.Account


class _TransactionBaseFields(_TransactionCoreFields, total=False):
    type: algopy.TransactionType
    type_bytes: algopy.Bytes


class _AssetTransferBaseFields(TypedDict, total=False):
    xfer_asset: algopy.Asset
    asset_amount: algopy.UInt64
    asset_sender: algopy.Account
    asset_receiver: algopy.Account
    asset_close_to: algopy.Account


class _PaymentBaseFields(TypedDict, total=False):
    receiver: algopy.Account
    amount: algopy.UInt64
    close_remainder_to: algopy.Account


class _AssetFreezeBaseFields(TypedDict, total=False):
    freeze_asset: algopy.Asset
    freeze_account: algopy.Account
    frozen: bool


class _AssetConfigBaseFields(TypedDict, total=False):
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


class _ApplicationCallCoreFields(TypedDict, total=False):
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


class _ApplicationCallBaseFields(_ApplicationCallCoreFields, total=False):
    app_args: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]
    accounts: typing.Callable[[algopy.UInt64 | int], algopy.Account]
    assets: typing.Callable[[algopy.UInt64 | int], algopy.Asset]
    apps: typing.Callable[[algopy.UInt64 | int], algopy.Application]
    approval_program_pages: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]
    clear_state_program_pages: typing.Callable[[algopy.UInt64 | int], algopy.Bytes]


class _ApplicationCallFields(_TransactionBaseFields, _ApplicationCallCoreFields, total=False):
    pass


class _KeyRegistrationBaseFields(TypedDict, total=False):
    vote_key: algopy.Bytes
    selection_key: algopy.Bytes
    vote_first: algopy.UInt64
    vote_last: algopy.UInt64
    vote_key_dilution: algopy.UInt64
    non_participation: bool
    state_proof_key: algopy.Bytes


class _TransactionFields(
    _TransactionBaseFields,
    _PaymentBaseFields,
    _KeyRegistrationBaseFields,
    _AssetConfigBaseFields,
    _AssetTransferBaseFields,
    _AssetFreezeBaseFields,
    _ApplicationCallBaseFields,
    total=False,
):
    pass


class AssetTransferFields(_TransactionBaseFields, _AssetTransferBaseFields, total=False):
    pass


class PaymentFields(_TransactionBaseFields, _PaymentBaseFields, total=False):
    pass


class AssetFreezeFields(_TransactionBaseFields, _AssetFreezeBaseFields, total=False):
    pass


class AssetConfigFields(_TransactionBaseFields, _AssetConfigBaseFields, total=False):
    pass


class ApplicationCallFields(_TransactionBaseFields, _ApplicationCallBaseFields, total=False):
    pass


class KeyRegistrationFields(_TransactionBaseFields, _KeyRegistrationBaseFields, total=False):
    pass


__all__ = [
    "ApplicationCallFields",
    "AssetConfigFields",
    "AssetFreezeFields",
    "AssetTransferFields",
    "KeyRegistrationFields",
    "PaymentFields",
    "_ApplicationCallBaseFields",
    "_ApplicationCallFields",
    "_AssetConfigBaseFields",
    "_AssetFreezeBaseFields",
    "_AssetTransferBaseFields",
    "_KeyRegistrationBaseFields",
    "_PaymentBaseFields",
    "_TransactionBaseFields",
    "_TransactionCoreFields",
    "_TransactionFields",
]
