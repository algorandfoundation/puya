from __future__ import annotations

import contextlib
from typing import Iterator, Sequence

from puyapy_mocks._ctx_state import ExecutionContextState, _ctx
from puyapy_mocks._primatives import Bytes, UInt64, convert_to_bytes
from puyapy_mocks._reference import Account


class ExecutionContext:
    def __init__(self, state: ExecutionContextState) -> None:
        self.state = state

    def set_args(self, *args: UInt64 | int | Bytes | bytes | str) -> None:
        self.state.args = list(map(convert_to_bytes, args))

    def logs(self) -> Sequence[bytes]:
        return self.state.logs

    def test_account(self, asset_id: int, amount: int) -> Account:
        account = Account("test")
        self.state.adjust_balance(account.address, asset_id, amount)
        return account

    def contract_account(self, asset_id: int, amount: int) -> Account:
        account = Account("contract")
        self.state.adjust_balance(account.address, asset_id, amount)
        return account


@contextlib.contextmanager
def execution_ctx() -> Iterator[ExecutionContext]:
    original_ctx = _ctx["active"]
    try:
        this_ctx = ExecutionContextState()
        _ctx["active"] = this_ctx
        yield ExecutionContext(this_ctx)
    finally:
        _ctx["active"] = original_ctx
