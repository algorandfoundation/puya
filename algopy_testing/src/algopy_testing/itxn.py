import typing
from dataclasses import dataclass

import algopy

from algopy_testing.context import get_test_context
from algopy_testing.enums import OnCompleteAction, TransactionType
from algopy_testing.models.account import Account
from algopy_testing.models.application import Application

# from algopy_testing.models.asset import Asset
from algopy_testing.models.asset import Asset
from algopy_testing.primitives.bytes import Bytes
from algopy_testing.primitives.string import String
from algopy_testing.primitives.uint64 import UInt64


@dataclass
class BaseInnerTransaction:
    def submit(self) -> object:
        context = get_test_context()

        if not context:
            raise RuntimeError("No test context found")

        context.add_inner_transaction(self)

        return self

    def copy(self) -> typing.Self:
        return self.__class__(**self.__dict__)


@dataclass
class InnerTransaction(BaseInnerTransaction):
    """Creates a set of fields used to submit an inner transaction of any type"""

    type: TransactionType | None = None
    receiver: Account | str | None = None
    amount: UInt64 | int | None = None
    close_remainder_to: Account | str | None = None
    vote_key: Bytes | bytes | None = None
    selection_key: Bytes | bytes | None = None
    vote_first: UInt64 | int | None = None
    vote_last: UInt64 | int | None = None
    vote_key_dilution: UInt64 | int | None = None
    non_participation: UInt64 | int | bool | None = None
    state_proof_key: Bytes | bytes | None = None
    config_asset: Asset | UInt64 | int | None = None
    total: UInt64 | int | None = None
    unit_name: String | Bytes | str | bytes | None = None
    asset_name: String | Bytes | str | bytes | None = None
    decimals: UInt64 | int | None = None
    default_frozen: bool | None = None
    url: String | Bytes | bytes | str | None = None
    metadata_hash: Bytes | bytes | None = None
    manager: Account | str | None = None
    reserve: Account | str | None = None
    freeze: Account | str | None = None
    clawback: Account | str | None = None
    xfer_asset: Asset | UInt64 | int | None = None
    asset_amount: UInt64 | int | None = None
    asset_sender: Account | str | None = None
    asset_receiver: Account | str | None = None
    asset_close_to: Account | str | None = None
    freeze_asset: Asset | UInt64 | int | None = None
    freeze_account: algopy.Account | str | None = None
    frozen: bool | None = None
    app_id: algopy.Application | algopy.UInt64 | int | None = None
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] | None = None
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] | None = None
    on_completion: OnCompleteAction | algopy.UInt64 | int | None = None
    global_num_uint: algopy.UInt64 | int | None = None
    global_num_bytes: algopy.UInt64 | int | None = None
    local_num_uint: algopy.UInt64 | int | None = None
    local_num_bytes: algopy.UInt64 | int | None = None
    extra_program_pages: algopy.UInt64 | int | None = None
    app_args: tuple[algopy.Bytes, ...] | None = None
    accounts: tuple[algopy.Account, ...] | None = None
    assets: tuple[algopy.Asset, ...] | None = None
    apps: tuple[algopy.Application, ...] | None = None
    sender: algopy.Account | None = None
    fee: algopy.UInt64 | int = 0
    note: algopy.String | algopy.Bytes | str | bytes | None = None
    rekey_to: algopy.Account | str | None = None


@dataclass
class Payment(BaseInnerTransaction):
    receiver: algopy.Account | None = None
    amount: algopy.UInt64 | None = None
    close_remainder_to: algopy.Account | None = None
    sender: algopy.Account | None = None
    fee: algopy.UInt64 | None = None
    note: algopy.String | None = None
    rekey_to: algopy.Account | None = None


@dataclass
class KeyRegistration(BaseInnerTransaction):
    vote_key: algopy.Bytes | None = None
    selection_key: algopy.Bytes | None = None
    vote_first: algopy.UInt64 | None = None
    vote_last: algopy.UInt64 | None = None
    vote_key_dilution: algopy.UInt64 | None = None
    non_participation: algopy.UInt64 | None = None
    state_proof_key: algopy.Bytes | None = None
    sender: algopy.Account | None = None
    fee: algopy.UInt64 | None = None
    note: algopy.String | None = None
    rekey_to: algopy.Account | None = None


@dataclass
class AssetConfig(BaseInnerTransaction):
    config_asset: Asset | None = None
    total: UInt64 | None = None
    unit_name: String | None = None
    asset_name: String | None = None
    decimals: UInt64 | None = None
    default_frozen: bool | None = None
    url: String | None = None
    metadata_hash: Bytes | None = None
    manager: Account | None = None
    reserve: Account | None = None
    freeze: Account | None = None
    clawback: Account | None = None
    sender: Account | None = None
    fee: UInt64 | None = None
    note: String | None = None
    rekey_to: Account | None = None


@dataclass
class AssetTransfer(BaseInnerTransaction):
    xfer_asset: Asset | None = None
    asset_amount: UInt64 | None = None
    asset_sender: Account | None = None
    asset_receiver: Account | None = None
    asset_close_to: Account | None = None
    sender: Account | None = None
    fee: UInt64 | None = None
    note: String | None = None
    rekey_to: Account | None = None


@dataclass
class AssetFreeze(BaseInnerTransaction):
    freeze_asset: Asset | None = None
    freeze_account: Account | None = None
    frozen: bool | None = None
    sender: Account | None = None
    fee: UInt64 | None = None
    note: String | None = None
    rekey_to: Account | None = None


@dataclass
class ApplicationCall(BaseInnerTransaction):
    app_id: Application | None = None
    approval_program: Bytes | None = None
    clear_state_program: Bytes | None = None
    on_completion: OnCompleteAction | None = None
    global_num_uint: UInt64 | None = None
    global_num_bytes: UInt64 | None = None
    local_num_uint: UInt64 | None = None
    local_num_bytes: UInt64 | None = None
    extra_program_pages: UInt64 | None = None
    app_args: object | None = None
    accounts: object | None = None
    assets: object | None = None
    apps: object | None = None
    sender: Account | None = None
    fee: UInt64 | None = None
    note: String | None = None
    rekey_to: Account | None = None


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
