from __future__ import annotations

import contextlib
from typing import Iterator, Sequence

import attrs

from puyapy_mocks._primatives import Bytes, UInt64

# from puyapy_mocks.op import Txn

__ctx: dict[str, ExecutionContext | None] = {"active": None}


def _convert_to_bytes(arg: UInt64 | int | Bytes | bytes | str) -> bytes:
    if isinstance(arg, (UInt64, int)):
        return int.to_bytes(int(arg), 8)
    elif isinstance(arg, Bytes):
        return bytes(arg)
    elif isinstance(arg, bytes):
        return arg
    elif isinstance(arg, str):
        return arg.encode()

    return NotImplemented


@attrs.define
class ExecutionContext:
    _args: list[bytes] = attrs.field(factory=list)
    _logs: list[bytes] = attrs.field(factory=list)

    def get_arg(self, index: int) -> bytes:
        return self._args[index]

    def log(self, *args: UInt64 | int | Bytes | bytes) -> None:
        self._logs.append(b"".join(map(_convert_to_bytes, args)))

    def set_args(self, *args: UInt64 | int | Bytes | bytes | str) -> None:
        self._args = list(map(_convert_to_bytes, args))

    def logs(self) -> Sequence[bytes]:
        return self._logs


def active_ctx() -> ExecutionContext:
    active = __ctx["active"]
    if active is None:
        raise Exception("No context available, begin a context with execution_ctx")
    return active


@contextlib.contextmanager
def execution_ctx() -> Iterator[ExecutionContext]:
    original_ctx = __ctx["active"]
    try:
        this_ctx = ExecutionContext()
        __ctx["active"] = this_ctx
        yield this_ctx
    finally:
        __ctx["active"] = original_ctx
