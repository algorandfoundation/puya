from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, TypeVar

if TYPE_CHECKING:
    # from algopy_testing.models.asset import Asset
    from algopy_testing.models.account import Account
    from algopy_testing.models.application import Application
    from algopy_testing.models.asset import Asset
    from algopy_testing.primitives.bytes import Bytes
    from algopy_testing.primitives.uint64 import UInt64

T = TypeVar("T")


class ITxnFields(TypedDict, total=False):
    sender: Account
    fee: UInt64
    first_valid: UInt64
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


@dataclass
class _ITxn:
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if not context.itxn_fields:
            raise ValueError(
                "`algopy.ITxn` fields are not set in the test context! "
                "Use `context.patch_itxn_fields()` to set the fields in your test setup."
            )
        if name not in context.itxn_fields:
            raise AttributeError(
                f"'Txn' object has no value set for attribute named '{name}'. "
                f"Use `context.patch_itxn_fields({name}=your_value)` to set the value "
                "in your test setup."
            )
        if not context.itxn_fields[name]:
            raise TypeError(
                f"The value for '{name}' in the test context is None. "
                f"Make sure to patch the global field '{name}' using your `AlgopyTestContext` "
                "instance."
            )

        return context.itxn_fields[name]


ITxn = _ITxn()
