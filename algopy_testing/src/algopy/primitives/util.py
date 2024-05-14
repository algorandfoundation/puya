from __future__ import annotations

from algopy import Bytes, UInt64


def as_int(value: object, *, max: int) -> int:  # noqa: A002
    """
    Returns the underlying int value for any numeric type up to UInt512

    Raises:
        TypeError: If `value` is not a numeric type
        ValueError: If not 0 <= `value` <= max
    """
    match value:
        case int(int_value):
            pass
        case UInt64(value=int_value):
            pass
        # TODO: add BigUInt and arc4 numerics
        case _:
            raise TypeError(f"value must be a numeric type, not {type(value).__name__!r}")
    if int_value < 0:
        raise ValueError(f"expected positive value, got {int_value}")
    if int_value > max:
        raise ValueError(f"expected value <= {max}, got: {int_value}")
    return int_value


def as_bytes(value: object, *, max_size: int) -> bytes:
    """
    Returns the underlying bytes value for bytes or Bytes type up to 4096

    Raises:
        TypeError: If `value` is not a bytes type
        ValueError: If not 0 <= `len(value)` <= max_size
    """
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
