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
    application_args: tuple[bytes, ...] | None = None
    accounts: tuple[str, ...] | None = None
    assets: tuple[int, ...] | None = None
    applications: tuple[int, ...] | None = None
    logs: tuple[bytes, ...] | None = None
    approval_program_pages: tuple[bytes, ...] | None = None
    clear_state_program_pages: tuple[bytes, ...] | None = None


class _Txn:
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        if name in TxnFields.__annotations__:
            context = get_test_context()
            if not context or not context.transaction_state:
                raise ValueError("Txn state is not set")
            return getattr(context.transaction_state, name)
        raise AttributeError(f"'Txn' object has no attribute '{name}'")


Txn = _Txn()
