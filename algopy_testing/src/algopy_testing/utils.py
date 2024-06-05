from __future__ import annotations

from algopy_testing import arc4
from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT8, MAX_UINT64, MAX_UINT512


def as_int(value: object, *, max: int | None) -> int:  # noqa: A002
    """
    Returns the underlying int value for any numeric type up to UInt512

    Raises:
        TypeError: If `value` is not a numeric type
        ValueError: If not 0 <= `value` <= max
    """

    from algopy_testing.primitives.biguint import BigUInt
    from algopy_testing.primitives.uint64 import UInt64

    match value:
        case int(int_value):
            pass
        case UInt64(value=int_value):
            pass
        case BigUInt(value=int_value):
            pass
        case arc4.UIntN():
            int_value = value.native.value
        case arc4.BigUIntN():
            int_value = value.native.value
        # TODO: add arc4 numerics
        case _:
            raise TypeError(f"value must be a numeric type, not {type(value).__name__!r}")
    if int_value < 0:
        raise ValueError(f"expected positive value, got {int_value}")
    if max is not None and int_value > max:
        raise ValueError(f"expected value <= {max}, got: {int_value}")
    return int_value


def as_int8(value: object) -> int:
    return as_int(value, max=MAX_UINT8)


def as_int64(value: object) -> int:
    return as_int(value, max=MAX_UINT64)


def as_int512(value: object) -> int:
    return as_int(value, max=MAX_UINT512)


def as_bytes(value: object, *, max_size: int = MAX_BYTES_SIZE) -> bytes:
    """
    Returns the underlying bytes value for bytes or Bytes type up to 4096

    Raises:
        TypeError: If `value` is not a bytes type
        ValueError: If not 0 <= `len(value)` <= max_size
    """
    from algopy_testing.primitives.bytes import Bytes

    match value:
        case bytes(bytes_value):
            pass
        case Bytes(value=bytes_value):
            pass
        case _:
            raise TypeError(f"value must be a bytes or Bytes type, not {type(value).__name__!r}")
    if len(bytes_value) > max_size:
        raise ValueError(f"expected value length <= {max_size}, got: {len(bytes_value)}")
    return bytes_value


def as_string(value: object) -> str:
    from algopy_testing.primitives.string import String

    match value:
        case str(string_value) | String(value=string_value):
            return string_value
        case arc4.String():
            return value.native.value
        case _:
            raise TypeError(f"value must be a string or String type, not {type(value).__name__!r}")


def int_to_bytes(x: int, pad_to: int | None = None) -> bytes:
    result = x.to_bytes((x.bit_length() + 7) // 8, "big")
    result = (
        b"\x00" * (pad_to - len(result)) if pad_to is not None and len(result) < pad_to else b""
    ) + result

    return result
