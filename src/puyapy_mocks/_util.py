from puyapy_mocks import Bytes, UInt64, convert_to_bytes
from puyapy_mocks._ctx_state import active_ctx


def log(*args: Bytes | bytes | UInt64 | int) -> None:
    active_ctx().logs.append(b"".join(map(convert_to_bytes, args)))
