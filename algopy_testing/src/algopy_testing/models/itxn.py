from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from algopy_testing.models.account import Account
    from algopy_testing.models.application import Application
    from algopy_testing.models.asset import Asset
    from algopy_testing.primitives.bytes import Bytes
    from algopy_testing.primitives.uint64 import UInt64

T = TypeVar("T")


@dataclass
class ITxnFields:
    sender: Account | None = None
    fee: UInt64 | None = None
    first_valid: UInt64 | None = None
    last_valid: UInt64 | None = None
    note: Bytes | None = None
    lease: Bytes | None = None
    receiver: Account | None = None
    amount: UInt64 | None = None
    close_remainder_to: Account | None = None
    vote_pk: Bytes | None = None
    selection_pk: Bytes | None = None
    vote_first: UInt64 | None = None
    vote_last: UInt64 | None = None
    vote_key_dilution: UInt64 | None = None
    type: Bytes | None = None
    type_enum: UInt64 | None = None
    xfer_asset: Asset | None = None
    asset_amount: UInt64 | None = None
    asset_sender: Account | None = None
    asset_receiver: Account | None = None
    asset_close_to: Account | None = None
    group_index: UInt64 | None = None
    tx_id: Bytes | None = None
    application_id: Application | None = None
    on_completion: UInt64 | None = None
    approval_program: Bytes | None = None
    clear_state_program: Bytes | None = None
    rekey_to: Account | None = None
    config_asset: Asset | None = None
    config_asset_total: UInt64 | None = None
    config_asset_decimals: UInt64 | None = None
    config_asset_default_frozen: bool | None = None
    config_asset_unit_name: Bytes | None = None
    config_asset_name: Bytes | None = None
    config_asset_url: Bytes | None = None
    config_asset_metadata_hash: Bytes | None = None
    config_asset_manager: Account | None = None
    config_asset_reserve: Account | None = None
    config_asset_freeze: Account | None = None
    config_asset_clawback: Account | None = None
    freeze_asset: Asset | None = None
    freeze_asset_account: Account | None = None
    freeze_asset_frozen: bool | None = None
    global_num_uint: UInt64 | None = None
    global_num_byte_slice: UInt64 | None = None
    local_num_uint: UInt64 | None = None
    local_num_byte_slice: UInt64 | None = None
    extra_program_pages: UInt64 | None = None
    nonparticipation: bool | None = None
    created_asset_id: Asset | None = None
    created_application_id: Application | None = None
    last_log: Bytes | None = None
    state_proof_pk: Bytes | None = None


class _Itxn:
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        if name in ITxnFields.__annotations__:
            context = get_test_context()
            if not context or not context.itxn_state:
                raise ValueError("ITxn fields are not set")
            return getattr(context.itxn_state, name)

        raise AttributeError(f"'Itxn' object has no attribute '{name}'")


Itxn = _Itxn()
