from puyapy_mocks import Bytes, UInt64
from puyapy_mocks._ctx import active_ctx


def log(*args: Bytes | bytes | UInt64 | int) -> None:
    active_ctx().log(*args)
