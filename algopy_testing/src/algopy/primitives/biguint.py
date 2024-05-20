from __future__ import annotations

import functools

from algopy.constants import MAX_BYTES_SIZE, MAX_UINT512, UNIT64_BYTES_LENGTH
from algopy.primitives.bytes import Bytes
from algopy.primitives.uint64 import UInt64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


@functools.total_ordering
class BigUInt:
    """
    A python implementation of an TEAL bigint type represented by AVM []byte type
    """

    __value: bytes  # underlying 'bytes' value representing the BigUInt

    def __init__(self, value: UInt64 | int = 0) -> None:
        self.__value = (
            _int_to_bytes(value.value, UNIT64_BYTES_LENGTH)
            if isinstance(value, UInt64)
            else _int_to_bytes(value)
        )

    def __repr__(self) -> str:
        return f"{self.value}u"

    def __str__(self) -> str:
        return str(self.value)

    # comparison operations should not error when comparing any uint type
    # e.g. UInt64, BigUInt, arc4.UInt*, arc4.BigUint*
    # however will raise a TypeError if compared to something that is not a numeric value
    # as this would be a compile error when compiled to TEAL
    def __eq__(self, other: object) -> bool:
        return _as_int512(self) == _as_int512(other)

    def __lt__(self, other: BigUInt | UInt64 | int) -> bool:
        return _as_int512(self) < _as_int512(other)

    def __bool__(self) -> bool:
        return bool(_as_int512(self))

    def __add__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(_as_int512(self) + _as_int512(other), "+")

    # the reflected dunder methods (__radd__, __rsub___, etc.) should only be called when the
    # BigUInt is on the right hand side and UInt64 or int on the left
    def __radd__(self, other: int | UInt64) -> BigUInt:
        return self + other

    def __sub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(_as_int512(self) - _as_int512(other), "-")

    def __rsub__(self, other: int | UInt64) -> BigUInt:
        return _as_biguint(other) - self

    def __mul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(_as_int512(self) * _as_int512(other), "*")

    def __rmul__(self, other: int | UInt64) -> BigUInt:
        return self * other

    def __floordiv__(self, denominator: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(_as_int512(self) // _as_int512(denominator), "//")

    def __rfloordiv__(self, numerator: int | UInt64) -> BigUInt:
        return _as_biguint(numerator) // self

    def __mod__(self, denominator: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(_as_int512(self) % _as_int512(denominator), "%")

    def __rmod__(self, numerator: int | UInt64) -> BigUInt:
        return _as_biguint(numerator) % self

    def __and__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        assert _as_int512(self) >= 0
        assert _as_int512(other) >= 0
        return BigUInt.from_bytes(self.bytes & _as_biguint(other).bytes)

    def __rand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self & other

    def __or__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        assert _as_int512(self) >= 0
        assert _as_int512(other) >= 0
        return BigUInt.from_bytes(self.bytes | _as_biguint(other).bytes)

    def __ror__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self | other

    def __xor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        assert _as_int512(self) >= 0
        assert _as_int512(other) >= 0
        return BigUInt.from_bytes(self.bytes ^ _as_biguint(other).bytes)

    def __rxor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self ^ other

    def __pos__(self) -> BigUInt:
        """
        Compute the unary positive of the BigUInt.

        Returns:
            BigUInt: The result of the unary positive operation.
        """
        return BigUInt(+_as_int512(self))

    @classmethod
    def from_bytes(cls, value: Bytes | bytes) -> BigUInt:
        """Construct an instance from the underlying bytes (no validation)"""
        result = cls()
        result.__value = _as_bytes(value)  # noqa: SLF001
        return result

    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""
        return Bytes(self.__value)

    @property
    def value(self) -> int:
        """Get the underlying int"""
        return _as_int(int.from_bytes(self.__value), None)


def _checked_result(result: int, op: str) -> BigUInt:
    """Ensures `result` is a valid BigUInt value

    Raises:
        ArithmeticError: If `result` of `op` is negative"""
    if result < 0:
        raise ArithmeticError(f"{op} underflows")
    return BigUInt(result)


def _as_int512(value: object) -> int:
    return _as_int(value, MAX_UINT512)


def _as_int(value: object, max_int: int | None) -> int:
    from algopy.primitives.util import as_int

    return as_int(value, max=max_int)


def _as_bytes(value: object) -> bytes:
    from algopy.primitives.util import as_bytes

    return as_bytes(value, max_size=MAX_BYTES_SIZE)


def _as_biguint(value: object) -> BigUInt:
    return BigUInt(value if (isinstance(value, UInt64)) else _as_int(value, None))


def _int_to_bytes(x: int, pad_to: int | None = None) -> bytes:
    x = _as_int(x, None)
    result = x.to_bytes((x.bit_length() + 7) // 8, "big")
    result = (
        b"\x00" * (pad_to - len(result)) if pad_to is not None and len(result) < pad_to else b""
    ) + result

    return result
