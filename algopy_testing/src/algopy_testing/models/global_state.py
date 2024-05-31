from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, TypeVar

if TYPE_CHECKING:
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
    current_application_id: algopy.UInt64
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
    def __getattr__(self, name: str) -> object:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if not context.global_fields:
            raise ValueError(
                "`algopy.Global` fields are not set in the test context! "
                "Use `context.patch_global_fields()` to set the fields in your test setup."
            )
        if name not in context.global_fields:
            raise AttributeError(
                f"'algopy.Global' object has no value set for attribute named '{name}'. "
                f"Use `context.patch_global_fields({name}=your_value)` to set the value "
                "in your test setup."
            )
        if not context.global_fields[name]:
            raise TypeError(
                f"The value for '{name}' in the test context is None. "
                f"Make sure to patch the global field '{name}' using your `AlgopyTestContext` "
                "instance."
            )

        return context.global_fields[name]


Global = _Global()
