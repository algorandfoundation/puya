from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from algopy.constants import MAX_UINT512
from algopy.primitives.bytes import Bytes

if TYPE_CHECKING:
    from algopy.primitives.uint64 import UInt64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


@functools.total_ordering
class BigUInt:
    """
    A python implementation of an AVM 64-bit unsigned integer
    """

    value: int  # underlying 'int' value representing the BigUInt

    def __init__(self, value: UInt64 | int = 0) -> None:
        self.value = _as_int512(value)

    def __repr__(self) -> str:
        return f"{self.value}u"

    def __str__(self) -> str:
        return str(self.value)

    # comparison operations should not error when comparing any uint type
    # e.g. UInt64, BigUInt, arc4.UInt*, arc4.BigUint*
    # however will raise a TypeError if compared to something that is not a numeric value
    # as this would be a compile error when compiled to TEAL
    def __eq__(self, other: object) -> bool:
        return self.value == _as_int512(other)

    def __lt__(self, other: BigUInt | UInt64 | int) -> bool:
        return self.value < _as_int512(other)

    def __bool__(self) -> bool:
        return self.value != 0

    def __add__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(self.value + _as_int512(other), "+")

    # the reflected dunder methods (__radd__, __rsub___, etc.) should only be called when the
    # BigUInt is on the right hand side and an int on the left
    def __radd__(self, other: int) -> BigUInt:
        return self + other

    def __sub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(self.value - _as_int512(other), "-")

    def __rsub__(self, other: int) -> BigUInt:
        return _as_biguint(other) - self

    def __mul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(self.value * _as_int512(other), "*")

    def __rmul__(self, other: int) -> BigUInt:
        return self * other

    def __floordiv__(self, denominator: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(self.value // _as_int512(denominator), "//")

    def __rfloordiv__(self, numerator: int) -> BigUInt:
        return _as_biguint(numerator) // self

    def __mod__(self, denominator: BigUInt | UInt64 | int) -> BigUInt:
        return _checked_result(self.value % _as_int512(denominator), "%")

    def __rmod__(self, numerator: int) -> BigUInt:
        return _as_biguint(numerator) % self

    def __and__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return BigUInt(self.value & _as_int512(other))

    def __rand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self & other

    def __or__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return BigUInt(self.value | _as_int512(other))

    def __ror__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self | other

    def __xor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return BigUInt(self.value ^ _as_int512(other))

    def __rxor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        return self ^ other

    def __index__(self) -> int:
        """
        Return the internal integer value of the BigUInt for use in indexing/slice expressions.

        Returns:
            int: The internal integer value of the BigUInt.
        """
        return self.value

    def __pos__(self) -> BigUInt:
        """
        Compute the unary positive of the BigUInt.

        Returns:
            BigUInt: The result of the unary positive operation.
        """
        return BigUInt(+self.value)

    @classmethod
    def from_bytes(cls, value: Bytes | bytes) -> BigUInt:
        """Construct an instance from the underlying bytes (no validation)"""
        return cls(int.from_bytes(value.value if (isinstance(value, Bytes)) else value))

    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""
        return Bytes(self.value.to_bytes((self.value.bit_length() + 7) // 8, "big"))


def _checked_result(result: int, op: str) -> BigUInt:
    """Ensures `result` is a valid BigUInt value

    Raises:
        ArithmeticError: If `result` of `op` is out of bounds"""
    if result < 0:
        raise ArithmeticError(f"{op} underflows")
    if result > MAX_UINT512:
        raise OverflowError(f"{op} overflows")
    return BigUInt(result)


def _as_int512(value: object) -> int:
    from algopy.primitives.util import as_int

    return as_int(value, max=MAX_UINT512)


def _as_biguint(value: object) -> BigUInt:
    return BigUInt(_as_int512(value))
