from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class TxnFields:
    sender: str | None = None
    fee: int | None = None
    first_valid: int | None = None
    first_valid_time: int | None = None
    last_valid: int | None = None
    note: bytes | None = None
    lease: bytes | None = None
    receiver: str | None = None
    amount: int | None = None
    close_remainder_to: str | None = None
    vote_pk: bytes | None = None
    selection_pk: bytes | None = None
    vote_first: int | None = None
    vote_last: int | None = None
    vote_key_dilution: int | None = None
    type: bytes | None = None
    type_enum: int | None = None
    xfer_asset: int | None = None
    asset_amount: int | None = None
    asset_sender: str | None = None
    asset_receiver: str | None = None
    asset_close_to: str | None = None
    group_index: int | None = None
    tx_id: bytes | None = None
    application_id: int | None = None
    on_completion: int | None = None
    num_app_args: int | None = None
    num_accounts: int | None = None
    approval_program: bytes | None = None
    clear_state_program: bytes | None = None
    rekey_to: str | None = None
    config_asset: int | None = None
    config_asset_total: int | None = None
    config_asset_decimals: int | None = None
    config_asset_default_frozen: bool | None = None
    config_asset_unit_name: bytes | None = None
    config_asset_name: bytes | None = None
    config_asset_url: bytes | None = None
    config_asset_metadata_hash: bytes | None = None
    config_asset_manager: str | None = None
    config_asset_reserve: str | None = None
    config_asset_freeze: str | None = None
    config_asset_clawback: str | None = None
    freeze_asset: int | None = None
    freeze_asset_account: str | None = None
    freeze_asset_frozen: bool | None = None
    num_assets: int | None = None
    num_applications: int | None = None
    global_num_uint: int | None = None
    global_num_byte_slice: int | None = None
    local_num_uint: int | None = None
    local_num_byte_slice: int | None = None
    extra_program_pages: int | None = None
    nonparticipation: bool | None = None
    num_logs: int | None = None
    created_asset_id: int | None = None
    created_application_id: int | None = None
    last_log: bytes | None = None
    state_proof_pk: bytes | None = None
    num_approval_program_pages: int | None = None
    num_clear_state_program_pages: int | None = None

    @staticmethod
    def application_args(a: int) -> bytes:
        raise NotImplementedError("'application_args' is not implemented")

    @staticmethod
    def accounts(a: int) -> str:
        raise NotImplementedError("'accounts' is not implemented")

    @staticmethod
    def assets(a: int) -> int:
        raise NotImplementedError("'assets' is not implemented")

    @staticmethod
    def applications(a: int) -> int:
        raise NotImplementedError("'applications' is not implemented")

    @staticmethod
    def logs(a: int) -> bytes:
        raise NotImplementedError("'logs' is not implemented")

    @staticmethod
    def approval_program_pages(a: int) -> bytes:
        raise NotImplementedError("'approval_program_pages' is not implemented")

    @staticmethod
    def clear_state_program_pages(a: int) -> bytes:
        raise NotImplementedError("'clear_state_program_pages' is not implemented")


class _Txn:
    def __getattr__(self, name: str) -> object:  # noqa: PLR0911
        from algopy_testing.context import get_test_context
        from algopy_testing.models.account import Account
        from algopy_testing.models.application import Application
        from algopy_testing.models.asset import Asset
        from algopy_testing.primitives.bytes import Bytes
        from algopy_testing.primitives.uint64 import UInt64

        if name in TxnFields.__annotations__:
            context = get_test_context()
            if not context or not context.transaction_state:
                raise ValueError("Txn state is not set")
            value = getattr(context.transaction_state, name)
            if value is None:
                return None
            if name in {
                "fee",
                "first_valid",
                "first_valid_time",
                "last_valid",
                "amount",
                "vote_first",
                "vote_last",
                "vote_key_dilution",
                "type_enum",
                "asset_amount",
                "group_index",
                "on_completion",
                "num_app_args",
                "num_accounts",
                "config_asset_total",
                "config_asset_decimals",
                "num_assets",
                "num_applications",
                "global_num_uint",
                "global_num_byte_slice",
                "local_num_uint",
                "local_num_byte_slice",
                "extra_program_pages",
                "num_logs",
                "created_asset_id",
                "created_application_id",
                "num_approval_program_pages",
                "num_clear_state_program_pages",
            }:
                return UInt64(value)
            if name in {
                "sender",
                "receiver",
                "close_remainder_to",
                "asset_sender",
                "asset_receiver",
                "asset_close_to",
                "rekey_to",
                "config_asset_manager",
                "config_asset_reserve",
                "config_asset_freeze",
                "config_asset_clawback",
                "freeze_asset_account",
            }:
                return Account(value)
            if name in {
                "note",
                "lease",
                "vote_pk",
                "selection_pk",
                "type",
                "tx_id",
                "approval_program",
                "clear_state_program",
                "config_asset_unit_name",
                "config_asset_name",
                "config_asset_url",
                "config_asset_metadata_hash",
                "last_log",
                "state_proof_pk",
            }:
                return Bytes(value)
            if name in {"xfer_asset", "application_id", "config_asset", "freeze_asset"}:
                return Asset(value)
            if name in {"created_application_id"}:
                return Application(value)
            return value
        raise AttributeError(f"'Txn' object has no attribute '{name}'")


Txn = _Txn()
