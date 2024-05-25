from __future__ import annotations

from typing import TypedDict, TypeVar, cast
from unittest.mock import MagicMock

from algopy._models.account import Account
from algopy._models.application import Application
from algopy._models.asset import Asset
from algopy._primitives.bytes import Bytes
from algopy._primitives.uint64 import UInt64

T = TypeVar("T")


class TxnOverrides(TypedDict, total=False):
    sender: Account
    fee: UInt64
    first_valid: UInt64
    first_valid_time: UInt64
    last_valid: UInt64
    note: Bytes
    lease: Bytes
    receiver: Account
    amount: UInt64
    close_remainder_to: Account
    vote_pk: Bytes
    selection_pk: Bytes
    vote_first: UInt64
    vote_last: UInt64
    vote_key_dilution: UInt64
    type: Bytes
    type_enum: UInt64
    xfer_asset: Asset
    asset_amount: UInt64
    asset_sender: Account
    asset_receiver: Account
    asset_close_to: Account
    group_index: UInt64
    tx_id: Bytes
    application_id: Application
    on_completion: UInt64
    approval_program: Bytes
    clear_state_program: Bytes
    rekey_to: Account
    config_asset: Asset
    config_asset_total: UInt64
    config_asset_decimals: UInt64
    config_asset_default_frozen: bool
    config_asset_unit_name: Bytes
    config_asset_name: Bytes
    config_asset_url: Bytes
    config_asset_metadata_hash: Bytes
    config_asset_manager: Account
    config_asset_reserve: Account
    config_asset_freeze: Account
    config_asset_clawback: Account
    freeze_asset: Asset
    freeze_asset_account: Account
    freeze_asset_frozen: bool
    global_num_uint: UInt64
    global_num_byte_slice: UInt64
    local_num_uint: UInt64
    local_num_byte_slice: UInt64
    extra_program_pages: UInt64
    nonparticipation: bool
    created_asset_id: Asset
    created_application_id: Application
    last_log: Bytes
    state_proof_pk: Bytes


class Txn:
    def __init__(self, **overrides: TxnOverrides):
        self._overrides = overrides

    def _get_property(self, name: str, default: T) -> T:
        return cast(T, self._overrides.get(name, MagicMock(spec=default)))

    @property
    def sender(self) -> Account:
        return self._get_property("sender", MagicMock(spec=Account))

    @property
    def fee(self) -> UInt64:
        return self._get_property("fee", MagicMock(spec=UInt64))

    @property
    def first_valid(self) -> UInt64:
        return self._get_property("first_valid", MagicMock(spec=UInt64))

    @property
    def first_valid_time(self) -> UInt64:
        return self._get_property("first_valid_time", MagicMock(spec=UInt64))

    @property
    def last_valid(self) -> UInt64:
        return self._get_property("last_valid", MagicMock(spec=UInt64))

    @property
    def note(self) -> Bytes:
        return self._get_property("note", MagicMock(spec=Bytes))

    @property
    def lease(self) -> Bytes:
        return self._get_property("lease", MagicMock(spec=Bytes))

    @property
    def receiver(self) -> Account:
        return self._get_property("receiver", MagicMock(spec=Account))

    @property
    def amount(self) -> UInt64:
        return self._get_property("amount", MagicMock(spec=UInt64))

    @property
    def close_remainder_to(self) -> Account:
        return self._get_property("close_remainder_to", MagicMock(spec=Account))

    @property
    def vote_pk(self) -> Bytes:
        return self._get_property("vote_pk", MagicMock(spec=Bytes))

    @property
    def selection_pk(self) -> Bytes:
        return self._get_property("selection_pk", MagicMock(spec=Bytes))

    @property
    def vote_first(self) -> UInt64:
        return self._get_property("vote_first", MagicMock(spec=UInt64))

    @property
    def vote_last(self) -> UInt64:
        return self._get_property("vote_last", MagicMock(spec=UInt64))

    @property
    def vote_key_dilution(self) -> UInt64:
        return self._get_property("vote_key_dilution", MagicMock(spec=UInt64))

    @property
    def type(self) -> Bytes:
        return self._get_property("type", MagicMock(spec=Bytes))

    @property
    def type_enum(self) -> UInt64:
        return self._get_property("type_enum", MagicMock(spec=UInt64))

    @property
    def xfer_asset(self) -> Asset:
        return self._get_property("xfer_asset", MagicMock(spec=Asset))

    @property
    def asset_amount(self) -> UInt64:
        return self._get_property("asset_amount", MagicMock(spec=UInt64))

    @property
    def asset_sender(self) -> Account:
        return self._get_property("asset_sender", MagicMock(spec=Account))

    @property
    def asset_receiver(self) -> Account:
        return self._get_property("asset_receiver", MagicMock(spec=Account))

    @property
    def asset_close_to(self) -> Account:
        return self._get_property("asset_close_to", MagicMock(spec=Account))

    @property
    def group_index(self) -> UInt64:
        return self._get_property("group_index", MagicMock(spec=UInt64))

    @property
    def tx_id(self) -> Bytes:
        return self._get_property("tx_id", MagicMock(spec=Bytes))

    @property
    def application_id(self) -> Application:
        return self._get_property("application_id", MagicMock(spec=Application))

    @property
    def on_completion(self) -> UInt64:
        return self._get_property("on_completion", MagicMock(spec=UInt64))

    @property
    def approval_program(self) -> Bytes:
        return self._get_property("approval_program", MagicMock(spec=Bytes))

    @property
    def clear_state_program(self) -> Bytes:
        return self._get_property("clear_state_program", MagicMock(spec=Bytes))

    @property
    def rekey_to(self) -> Account:
        return self._get_property("rekey_to", MagicMock(spec=Account))

    @property
    def config_asset(self) -> Asset:
        return self._get_property("config_asset", MagicMock(spec=Asset))

    @property
    def config_asset_total(self) -> UInt64:
        return self._get_property("config_asset_total", MagicMock(spec=UInt64))

    @property
    def config_asset_decimals(self) -> UInt64:
        return self._get_property("config_asset_decimals", MagicMock(spec=UInt64))

    @property
    def config_asset_default_frozen(self) -> bool:
        return self._get_property("config_asset_default_frozen", MagicMock(spec=bool))

    @property
    def config_asset_unit_name(self) -> Bytes:
        return self._get_property("config_asset_unit_name", MagicMock(spec=Bytes))

    @property
    def config_asset_name(self) -> Bytes:
        return self._get_property("config_asset_name", MagicMock(spec=Bytes))

    @property
    def config_asset_url(self) -> Bytes:
        return self._get_property("config_asset_url", MagicMock(spec=Bytes))

    @property
    def config_asset_metadata_hash(self) -> Bytes:
        return self._get_property("config_asset_metadata_hash", MagicMock(spec=Bytes))

    @property
    def config_asset_manager(self) -> Account:
        return self._get_property("config_asset_manager", MagicMock(spec=Account))

    @property
    def config_asset_reserve(self) -> Account:
        return self._get_property("config_asset_reserve", MagicMock(spec=Account))

    @property
    def config_asset_freeze(self) -> Account:
        return self._get_property("config_asset_freeze", MagicMock(spec=Account))

    @property
    def config_asset_clawback(self) -> Account:
        return self._get_property("config_asset_clawback", MagicMock(spec=Account))

    @property
    def freeze_asset(self) -> Asset:
        return self._get_property("freeze_asset", MagicMock(spec=Asset))

    @property
    def freeze_asset_account(self) -> Account:
        return self._get_property("freeze_asset_account", MagicMock(spec=Account))

    @property
    def freeze_asset_frozen(self) -> bool:
        return self._get_property("freeze_asset_frozen", MagicMock(spec=bool))

    @property
    def global_num_uint(self) -> UInt64:
        return self._get_property("global_num_uint", MagicMock(spec=UInt64))

    @property
    def global_num_byte_slice(self) -> UInt64:
        return self._get_property("global_num_byte_slice", MagicMock(spec=UInt64))

    @property
    def local_num_uint(self) -> UInt64:
        return self._get_property("local_num_uint", MagicMock(spec=UInt64))

    @property
    def local_num_byte_slice(self) -> UInt64:
        return self._get_property("local_num_byte_slice", MagicMock(spec=UInt64))

    @property
    def extra_program_pages(self) -> UInt64:
        return self._get_property("extra_program_pages", MagicMock(spec=UInt64))

    @property
    def nonparticipation(self) -> bool:
        return self._get_property("nonparticipation", MagicMock(spec=bool))

    @property
    def created_asset_id(self) -> Asset:
        return self._get_property("created_asset_id", MagicMock(spec=Asset))

    @property
    def created_application_id(self) -> Application:
        return self._get_property("created_application_id", MagicMock(spec=Application))

    @property
    def last_log(self) -> Bytes:
        return self._get_property("last_log", MagicMock(spec=Bytes))

    @property
    def state_proof_pk(self) -> Bytes:
        return self._get_property("state_proof_pk", MagicMock(spec=Bytes))

    @staticmethod
    def application_args(_a: UInt64 | int, /) -> Bytes:
        return MagicMock(spec=Bytes)

    @staticmethod
    def accounts(_a: UInt64 | int, /) -> Account:
        return MagicMock(spec=Account)

    @staticmethod
    def assets(_a: UInt64 | int, /) -> Asset:
        return MagicMock(spec=Asset)

    @staticmethod
    def applications(_a: UInt64 | int, /) -> Application:
        return MagicMock(spec=Application)

    @staticmethod
    def logs(_a: UInt64 | int, /) -> Bytes:
        return MagicMock(spec=Bytes)

    @staticmethod
    def approval_program_pages(_a: UInt64 | int, /) -> Bytes:
        return MagicMock(spec=Bytes)

    @staticmethod
    def clear_state_program_pages(_a: UInt64 | int, /) -> Bytes:
        return MagicMock(spec=Bytes)
