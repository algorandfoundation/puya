from __future__ import annotations

import functools

from algopy_testing.constants import MAX_UINT64
from algopy_testing.utils import as_int64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


@functools.total_ordering
class UInt64:
    """
    A python implementation of an AVM 64-bit unsigned integer
    """

    value: int  # underlying 'int' value representing the UInt64

    def __init__(self, value: int = 0) -> None:
        self.value = as_int64(value)

    def __repr__(self) -> str:
        return f"{self.value}u"

    def __str__(self) -> str:
        return str(self.value)

    # comparison operations should not error when comparing any uint type
    # e.g. UInt64, BigUInt, arc4.UInt*, arc4.BigUint*
    # however will raise a TypeError if compared to something that is not a numeric value
    # as this would be a compile error when compiled to TEAL
    def __eq__(self, other: object) -> bool:
        maybe_int = _as_maybe_uint64(other)
        # returning NotImplemented here will allow BigUInt to handle larger comparisons
        if maybe_int is None:
            return NotImplemented
        return self.value == maybe_int

    def __lt__(self, other: int | UInt64) -> bool:
        maybe_int = _as_maybe_uint64(other)
        # returning NotImplemented here will allow BigUInt to handle larger comparisons
        if maybe_int is None:
            return NotImplemented
        return self.value < maybe_int

    def __bool__(self) -> bool:
        return self.value != 0

    def __add__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        # returning NotImplemented here will allow BigUInt (and others) to upcast
        # a BigUint + UInt64 operation
        if maybe_int is None:
            return NotImplemented
        return _checked_result(self.value + maybe_int, "+")

    # the reflected dunder methods (__radd__, __rsub___, etc.) should only be called when the
    # UInt64 is on the right hand side and an int on the left
    def __radd__(self, other: int) -> UInt64:
        return self + other

    def __sub__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        if maybe_int is None:
            return NotImplemented
        return _checked_result(self.value - maybe_int, "-")

    def __rsub__(self, other: int) -> UInt64:
        return _as_uint64(other) - self

    def __mul__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        if maybe_int is None:
            return NotImplemented
        return _checked_result(self.value * maybe_int, "*")

    def __rmul__(self, other: int) -> UInt64:
        return self * other

    def __floordiv__(self, denominator: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(denominator)
        if maybe_int is None:
            return NotImplemented
        return _checked_result(self.value // maybe_int, "//")

    def __rfloordiv__(self, numerator: int) -> UInt64:
        return _as_uint64(numerator) // self

    def __mod__(self, denominator: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(denominator)
        if maybe_int is None:
            return NotImplemented

        return _checked_result(self.value % maybe_int, "%")

    def __rmod__(self, numerator: int) -> UInt64:
        return _as_uint64(numerator) % self

    def __pow__(self, exp: int | UInt64, modulo: int | UInt64 | None = None) -> UInt64:
        exp_int = _as_maybe_uint64(exp)
        if exp_int is None:
            return NotImplemented
        if modulo is not None:
            return NotImplemented
        if self.value == 0 and exp_int == 0:
            raise ArithmeticError("UInt64(0)**UInt64(0) is undefined")
        return _checked_result(self.value**exp_int, "**")

    def __rpow__(self, base: int, modulo: int | UInt64 | None = None) -> UInt64:
        return pow(_as_uint64(base), self, modulo)

    def __and__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        if maybe_int is None:
            return NotImplemented
        return UInt64(self.value & maybe_int)

    def __rand__(self, other: int) -> UInt64:
        return self & other

    def __or__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        if maybe_int is None:
            return NotImplemented
        return UInt64(self.value | maybe_int)

    def __ror__(self, other: int | UInt64) -> UInt64:
        return self | other

    def __xor__(self, other: int | UInt64) -> UInt64:
        maybe_int = _as_maybe_uint64(other)
        if maybe_int is None:
            return NotImplemented
        return UInt64(self.value ^ maybe_int)

    def __rxor__(self, other: int | UInt64) -> UInt64:
        return self ^ other

    def __lshift__(self, other: int | UInt64) -> UInt64:
        shift = as_int64(other)
        if shift > 63:
            raise ArithmeticError("expected shift <= 63")
        return UInt64((self.value << shift) & MAX_UINT64)

    def __rlshift__(self, other: int | UInt64) -> UInt64:
        return _as_uint64(other) << self

    def __rshift__(self, other: int | UInt64) -> UInt64:
        shift = as_int64(other)
        if shift > 63:
            raise ArithmeticError("expected shift <= 63")
        return UInt64((self.value >> shift) & MAX_UINT64)

    def __rrshift__(self, other: int | UInt64) -> UInt64:
        return _as_uint64(other) >> self

    def __invert__(self) -> UInt64:
        """
        Compute the bitwise inversion of the UInt64.

        Returns:
            UInt64: The result of the bitwise inversion operation.
        """
        return UInt64(~self.value & MAX_UINT64)

    def __index__(self) -> int:
        """
        Return the internal integer value of the UInt64 for use in indexing/slice expressions.

        Returns:
            int: The internal integer value of the UInt64.
        """
        return self.value

    def __pos__(self) -> UInt64:
        """
        Compute the unary positive of the UInt64.

        Returns:
            UInt64: The result of the unary positive operation.
        """
        return UInt64(+self.value)

    def __hash__(self) -> int:
        return hash(self.value)


def _as_maybe_uint64(value: object) -> int | None:
    """Returns int value if `value` is an int or UInt64, otherwise None"""
    match value:
        case int(int_value):
            return as_int64(int_value)
        case UInt64(value=int_value):
            return int_value
        case _:
            return None


def _checked_result(result: int, op: str) -> UInt64:
    """Ensures `result` is a valid UInt64 value

    Raises:
        ArithmeticError: If `result` of `op` is out of bounds"""
    if result < 0:
        raise ArithmeticError(f"{op} underflows")
    if result > MAX_UINT64:
        raise OverflowError(f"{op} overflows")
    return UInt64(result)


def _as_uint64(value: object) -> UInt64:
    return UInt64(as_int64(value))
