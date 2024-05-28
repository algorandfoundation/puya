from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class GlobalFields:
    min_txn_fee: int | None = None
    min_balance: int | None = None
    max_txn_life: int | None = None
    zero_address: str | None = None
    group_size: int | None = None
    logic_sig_version: int | None = None
    round: int | None = None
    latest_timestamp: int | None = None
    current_application_id: int | None = None
    creator_address: str | None = None
    current_application_address: str | None = None
    group_id: bytes | None = None
    caller_application_id: int | None = None
    caller_application_address: str | None = None
    asset_create_min_balance: int | None = None
    asset_opt_in_min_balance: int | None = None
    genesis_hash: bytes | None = None

    @staticmethod
    def opcode_budget() -> int:
        raise NotImplementedError("opcode_budget is not implemented. Please mock it in your test.")


class _Global:
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context
        from algopy_testing.models.account import Account
        from algopy_testing.primitives.bytes import Bytes
        from algopy_testing.primitives.uint64 import UInt64

        if name in GlobalFields.__annotations__:
            context = get_test_context()
            if not context or not context.global_state:
                raise ValueError("Global state is not set")
            value = getattr(context.global_state, name)
            if value is None:
                return None
            if name in {
                "min_txn_fee",
                "min_balance",
                "max_txn_life",
                "group_size",
                "logic_sig_version",
                "round",
                "latest_timestamp",
                "current_application_id",
                "caller_application_id",
                "asset_create_min_balance",
                "asset_opt_in_min_balance",
            }:
                return UInt64(value)
            if name in {
                "zero_address",
                "creator_address",
                "current_application_address",
                "caller_application_address",
            }:
                return Account(value)
            if name in {"group_id", "genesis_hash"}:
                return Bytes(value)
            return value
        raise AttributeError(f"'Global' object has no attribute '{name}'")


Global = _Global()
