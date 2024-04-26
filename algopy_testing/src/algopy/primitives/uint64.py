from __future__ import annotations
from algopy.primitives.constants import MAX_UINT64_BIT_SHIFT, MAX_UINT64
from algopy.error.uint64 import UInt64BitShiftOverflowError, UInt64OverflowError, UInt64UnderflowError, UInt64ZeroDivisionError


class UInt64:
    """
    A 64-bit unsigned integer, one of the primary data types on the AVM.
    """
    _value: int

    def __init__(self, value: int = 0) -> None:
        if not isinstance(value, int):
            raise TypeError(f"Value must be an integer, not {type(value).__name__}")
        if value < 0:
            raise UInt64UnderflowError(value)
        if value > MAX_UINT64:
            raise UInt64OverflowError(value)
        self._value = value

    def _get_value(self, other: int | UInt64) -> int:
        if not isinstance(other, (int, UInt64)):
            raise TypeError(f"Value must be an integer or UInt64, not {type(other).__name__}")

        return other._value if isinstance(other, UInt64) else other

    def __repr__(self) -> str:
        return f"UInt64({self._value})"

    def __eq__(self, other: int | UInt64) -> bool:
        return self._value == self._get_value(other)

    def __ne__(self, other: int | UInt64) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: int | UInt64) -> bool:
        return self._value < self._get_value(other)

    def __le__(self, other: int | UInt64) -> bool:
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other: int | UInt64) -> bool:
        return not self.__le__(other)

    def __ge__(self, other: int | UInt64) -> bool:
        return not self.__lt__(other)

    def __bool__(self) -> bool:
        return self._value != 0

    def __add__(self, other: int | UInt64) -> UInt64:
        result = self._value + self._get_value(other)
        if result > MAX_UINT64:
            raise OverflowError("UInt64 addition result exceeds maximum value")
        return UInt64(result)

    def __radd__(self, other: int) -> UInt64:
        return self.__add__(other)

    def __sub__(self, other: int | UInt64) -> UInt64:
        result = self._value - self._get_value(other)
        if result < 0:
            raise ValueError("UInt64 subtraction result is negative")
        return UInt64(result)

    def __rsub__(self, other: int) -> UInt64:
        result = other - self._value
        if result < 0:
            raise ValueError("UInt64 subtraction result is negative")
        return UInt64(result)

    def __mul__(self, other: int | UInt64) -> UInt64:
        result = self._value * self._get_value(other)
        if result > MAX_UINT64:
            raise OverflowError("UInt64 multiplication result exceeds maximum value")
        return UInt64(result)

    def __rmul__(self, other: int) -> UInt64:
        return self.__mul__(other)

    def __floordiv__(self, other: int | UInt64) -> UInt64:
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        return UInt64(self._value // other_value)

    def __rfloordiv__(self, other: int) -> UInt64:
        if self._value == 0:
            raise UInt64ZeroDivisionError(self._value)
        return UInt64(other // self._value)

    def __mod__(self, other: int | UInt64) -> UInt64:
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        return UInt64(self._value % other_value)

    def __rmod__(self, other: int) -> UInt64:
        if self._value == 0:
            raise UInt64ZeroDivisionError(self._value)
        return UInt64(other % self._value)

    def __pow__(self, other: int | UInt64, modulo: int | UInt64 | None = None) -> UInt64:
        exp = self._get_value(other)
        if modulo is not None:
            mod = self._get_value(modulo)
            result = pow(self._value, exp, mod)
        else:
            result = pow(self._value, exp)
        if result > MAX_UINT64:
            raise OverflowError("UInt64 power result exceeds maximum value")
        return UInt64(result)

    def __lshift__(self, other: int | UInt64) -> UInt64:
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        result = self._value << shift
        if result > MAX_UINT64:
            raise OverflowError("UInt64 left shift result exceeds maximum value")
        return UInt64(result)

    def __rshift__(self, other: int | UInt64) -> UInt64:
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        return UInt64(self._value >> shift)

    def __and__(self, other: int | UInt64) -> UInt64:
        return UInt64(self._value & self._get_value(other))

    def __or__(self, other: int | UInt64) -> UInt64:
        return UInt64(self._value | self._get_value(other))

    def __xor__(self, other: int | UInt64) -> UInt64:
        return UInt64(self._value ^ self._get_value(other))

    def __invert__(self) -> UInt64:
        return UInt64(~self._value & MAX_UINT64)

    def __index__(self) -> int:
        return self._value

    def __pos__(self) -> UInt64:
        return UInt64(+self._value)

    def __iadd__(self, other: int | UInt64) -> UInt64:
        result = self._value + self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        self._value = result
        return self

    def __isub__(self, other: int | UInt64) -> UInt64:
        result = self._value - self._get_value(other)
        if result < 0:
            raise UInt64UnderflowError(result)
        self._value = result
        return self

    def __imul__(self, other: int | UInt64) -> UInt64:
        result = self._value * self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        self._value = result
        return self

    def __ifloordiv__(self, other: int | UInt64) -> UInt64:
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        self._value //= other_value
        return self

    def __imod__(self, other: int | UInt64) -> UInt64:
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        self._value %= other_value
        return self

    def __ipow__(self, other: int | UInt64, modulo: int | UInt64 | None = None) -> UInt64:
        exp = self._get_value(other)
        if modulo is not None:
            mod = self._get_value(modulo)
            result = pow(self._value, exp, mod)
        else:
            result = pow(self._value, exp)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        self._value = result
        return self

    def __ilshift__(self, other: int | UInt64) -> UInt64:
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        result = self._value << shift
        if result > MAX_UINT64:
            raise UInt64BitShiftOverflowError(self._value, shift)
        self._value = result
        return self

    def __irshift__(self, other: int | UInt64) -> UInt64:
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        self._value >>= shift
        return self

    def __iand__(self, other: int | UInt64) -> UInt64:
        self._value &= self._get_value(other)
        return self

    def __ixor__(self, other: int | UInt64) -> UInt64:
        self._value ^= self._get_value(other)
        return self

    def __ior__(self, other: int | UInt64) -> UInt64:
        self._value |= self._get_value(other)
        return self

    def __rlshift__(self, other: int) -> UInt64:
        shift = other
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        result = self._value << shift
        if result > MAX_UINT64:
            raise UInt64BitShiftOverflowError(self._value, shift)
        return UInt64(result)

    def __rrshift__(self, other: int) -> UInt64:
        shift = other
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise ValueError("Shift amount must be between 0 and 63")
        return UInt64(self._value >> shift)

    def __rand__(self, other: int) -> UInt64:
        return UInt64(self._value & other)

    def __rxor__(self, other: int) -> UInt64:
        return UInt64(self._value ^ other)

    def __ror__(self, other: int) -> UInt64:
        return UInt64(self._value | other)
