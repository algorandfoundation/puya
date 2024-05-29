from hashlib import sha256

from algopy import Bytes


def int_to_bytes(x: int) -> bytes:
    return x.to_bytes((x.bit_length() + 7) // 8, "big")


def get_sha256_hash(v: Bytes) -> Bytes:
    return Bytes(sha256(v.value).digest())
