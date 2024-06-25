from hashlib import sha256

from algopy import Bytes


def int_to_bytes(x: int, pad_to: int | None = None) -> bytes:
    result = x.to_bytes((x.bit_length() + 7) // 8, "big")
    result = (
        b"\x00" * (pad_to - len(result)) if pad_to is not None and len(result) < pad_to else b""
    ) + result

    return result


def get_sha256_hash(v: Bytes) -> Bytes:
    return Bytes(sha256(v.value).digest())
