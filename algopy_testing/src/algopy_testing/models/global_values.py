from __future__ import annotations

import time
import typing
from dataclasses import dataclass
from typing import TypedDict, TypeVar

import algosdk

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    import algopy

T = TypeVar("T")


class GlobalFields(TypedDict, total=False):
    min_txn_fee: algopy.UInt64
    min_balance: algopy.UInt64
    max_txn_life: algopy.UInt64
    zero_address: algopy.Account
    group_size: algopy.UInt64
    logic_sig_version: algopy.UInt64
    round: algopy.UInt64
    latest_timestamp: algopy.UInt64
    current_application_id: algopy.Application
    creator_address: algopy.Account
    current_application_address: algopy.Account
    group_id: algopy.Bytes
    caller_application_id: algopy.Application
    caller_application_address: algopy.Account
    asset_create_min_balance: algopy.UInt64
    asset_opt_in_min_balance: algopy.UInt64
    genesis_hash: algopy.Bytes
    opcode_budget: Callable[[], int]


@dataclass
class _Global:
    def __getattr__(self, name: str) -> typing.Any:
        import algopy

        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )

        if name == "latest_timestamp" and context._global_fields.get(name) is None:
            return algopy.UInt64(int(time.time()))

        if name == "group_size" and context._global_fields.get(name) is None:
            return algopy.UInt64(len(context.get_transaction_group()))

        if name == "zero_address" and context._global_fields.get(name) is None:
            return algopy.Account(algosdk.constants.ZERO_ADDRESS)

        if name not in context._global_fields:
            raise AttributeError(
                f"'algopy.Global' object has no value set for attribute named '{name}'. "
                f"Use `context.patch_global_fields({name}=your_value)` to set the value "
                "in your test setup."
            )

        return context._global_fields[name]  # type: ignore[literal-required]


Global = _Global()
