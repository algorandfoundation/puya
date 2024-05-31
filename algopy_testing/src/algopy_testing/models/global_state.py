from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

    from algopy_testing.models.account import Account
    from algopy_testing.models.application import Application
    from algopy_testing.primitives.bytes import Bytes
    from algopy_testing.primitives.uint64 import UInt64

T = TypeVar("T")


class GlobalFieldsKwargs(TypedDict, total=False):
    min_txn_fee: UInt64
    min_balance: UInt64
    max_txn_life: UInt64
    zero_address: Account
    group_size: UInt64
    logic_sig_version: UInt64
    round: UInt64
    latest_timestamp: UInt64
    current_application_id: UInt64
    creator_address: Account
    current_application_address: Account
    group_id: Bytes
    caller_application_id: Application
    caller_application_address: Account
    asset_create_min_balance: UInt64
    asset_opt_in_min_balance: UInt64
    genesis_hash: Bytes


@dataclass
class GlobalFields:
    min_txn_fee: UInt64 | None = None
    min_balance: UInt64 | None = None
    max_txn_life: UInt64 | None = None
    zero_address: Account | None = None
    group_size: UInt64 | None = None
    logic_sig_version: UInt64 | None = None
    round: UInt64 | None = None
    latest_timestamp: UInt64 | None = None
    current_application_id: UInt64 | None = None
    creator_address: Account | None = None
    current_application_address: Account | None = None
    group_id: Bytes | None = None
    caller_application_id: Application | None = None
    caller_application_address: Account | None = None
    asset_create_min_balance: UInt64 | None = None
    asset_opt_in_min_balance: UInt64 | None = None
    genesis_hash: Bytes | None = None
    opcode_budget: Callable[[], int] | None = None


class _Global:
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        if name in GlobalFields.__annotations__:
            context = get_test_context()
            if not context or not context.global_fields:
                raise ValueError("Global state is not set")
            return getattr(context.global_fields, name)

        raise AttributeError(f"'Global' object has no attribute '{name}'")


Global = _Global()
