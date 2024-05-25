from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from algopy_testing.context import get_blockchain_context

if TYPE_CHECKING:
    from algopy._models.account import Account
    from algopy._models.application import Application
    from algopy._primitives.bytes import Bytes
    from algopy._primitives.uint64 import UInt64

T = TypeVar("T")


class Global:
    def _get_global_from_context(self) -> Global:
        context = get_blockchain_context()

        if not context or not context.global_state:
            raise ValueError("Test context is not available")

        return context.global_state

    @property
    def min_txn_fee(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.min_txn_fee

    @property
    def min_balance(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.min_balance

    @property
    def max_txn_life(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.max_txn_life

    @property
    def zero_address(self) -> Account:
        ctx = self._get_global_from_context()
        return ctx.zero_address

    @property
    def group_size(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.group_size

    @property
    def logic_sig_version(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.logic_sig_version

    @property
    def round(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.round

    @property
    def latest_timestamp(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.latest_timestamp

    @property
    def current_application_id(self) -> Application:
        ctx = self._get_global_from_context()
        return ctx.current_application_id

    @property
    def creator_address(self) -> Account:
        ctx = self._get_global_from_context()
        return ctx.creator_address

    @property
    def current_application_address(self) -> Account:
        ctx = self._get_global_from_context()
        return ctx.current_application_address

    @property
    def group_id(self) -> Bytes:
        ctx = self._get_global_from_context()
        return ctx.group_id

    @property
    def caller_application_id(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.caller_application_id

    @property
    def caller_application_address(self) -> Account:
        ctx = self._get_global_from_context()
        return ctx.caller_application_address

    @property
    def asset_create_min_balance(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.asset_create_min_balance

    @property
    def asset_opt_in_min_balance(self) -> UInt64:
        ctx = self._get_global_from_context()
        return ctx.asset_opt_in_min_balance

    @property
    def genesis_hash(self) -> Bytes:
        ctx = self._get_global_from_context()
        return ctx.genesis_hash

    @staticmethod
    def opcode_budget() -> UInt64:
        raise NotImplementedError(
            "The 'opcode_budget' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )
