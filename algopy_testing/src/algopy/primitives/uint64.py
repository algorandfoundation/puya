from __future__ import annotations

from typing import Self

from algopy.error.uint64 import (
    UInt64BitShiftInvalidValueError,
    UInt64BitShiftOverflowError,
    UInt64InvalidValueError,
    UInt64OverflowError,
    UInt64UnderflowError,
    UInt64ZeroDivisionError,
)
from algopy.primitives.constants import MAX_UINT64, MAX_UINT64_BIT_SHIFT


class UInt64:
    """
    A 64-bit unsigned integer, one of the primary data types on the AVM.
    """

    value: int  # Raw 'int' value representing the UInt64

    def __init__(self, value: int = 0) -> None:
        """
        Initialize a UInt64 with a Python int literal or an int variable
        declared at the module level.

        Args:
            value (int, optional): The initial value of the UInt64. Defaults to 0.

        Raises:
            UInt64InvalidValueError: If the provided value is not an integer.
            UInt64UnderflowError: If the provided value is negative.
            UInt64OverflowError: If the provided value exceeds the maximum value for a UInt64.
        """
        if not isinstance(value, int):
            raise UInt64InvalidValueError(f"Value must be an integer, not {type(value).__name__}")
        if value < 0:
            raise UInt64UnderflowError(value)
        if value > MAX_UINT64:
            raise UInt64OverflowError(value)
        self.value = value

    def _get_value(self, other: int | UInt64 | object) -> int:
        """
        Get the internal integer value of the provided object, whether it's an int or a UInt64.

        Args:
            other (int | UInt64): The object to get the value from.

        Raises:
            UInt64InvalidValueError: If the provided object is neither an int nor a UInt64.

        Returns:
            int: The internal integer value of the provided object.
        """
        if not isinstance(other, int | UInt64):
            raise UInt64InvalidValueError(
                f"Value must be an integer or UInt64, not {type(other).__name__}"
            )

        return other.value if isinstance(other, UInt64) else other

    def __repr__(self) -> str:
        """
        Return a string representation of the UInt64 object.

        Returns:
            str: A string representation of the UInt64 object in the format "UInt64(value)".
        """
        return f"UInt64({self.value})"

    def __eq__(self, other: object) -> bool:
        """
        Check if the UInt64 is equal to another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is equal to the other object, False otherwise.
        """
        return self.value == self._get_value(other)

    def __ne__(self, other: object) -> bool:
        """
        Check if the UInt64 is not equal to another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is not equal to the other object, False otherwise.
        """
        return not self.__eq__(other)

    def __le__(self, other: int | UInt64) -> bool:
        """
        Check if the UInt64 is less than or equal to another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is less than or equal to the other object, False otherwise.
        """
        return self.__lt__(other) or self.__eq__(other)

    def __lt__(self, other: int | UInt64) -> bool:
        """
        Check if the UInt64 is less than another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is less than the other object, False otherwise.
        """
        return self.value < self._get_value(other)

    def __ge__(self, other: int | UInt64) -> bool:
        """
        Check if the UInt64 is greater than or equal to another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is greater than or equal to the other object, False otherwise.
        """
        return not self.__lt__(other)

    def __gt__(self, other: int | UInt64) -> bool:
        """
        Check if the UInt64 is greater than another UInt64 or int.

        Args:
            other (int | UInt64): The object to compare with.

        Returns:
            bool: True if the UInt64 is greater than the other object, False otherwise.
        """
        return not self.__le__(other)

    def __bool__(self) -> bool:
        """
        Check if the UInt64 is non-zero.

        Returns:
            bool: True if the UInt64 is non-zero, False otherwise.
        """
        return self.value != 0

    def __add__(self, other: int | UInt64) -> UInt64:
        """
        Add the UInt64 to another UInt64 or int.

        Args:
            other (int | UInt64): The object to add to the UInt64.

        Raises:
            UInt64OverflowError: If the addition result exceeds the maximum value for a UInt64.

        Returns:
            UInt64: The result of the addition.
        """
        result = self.value + self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        return UInt64(result)

    def __radd__(self, other: int) -> UInt64:
        """
        Add an int to the UInt64.

        Args:
            other (int): The int to add to the UInt64.

        Returns:
            UInt64: The result of the addition.
        """
        return self.__add__(other)

    def __iadd__(self, other: int | UInt64) -> Self:
        """
        In-place addition of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to add to the UInt64.

        Raises:
            UInt64OverflowError: If the addition result exceeds the maximum value for a UInt64.

        Returns:
            Self: The result of the in-place addition.
        """
        result = self.value + self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        self.value = result
        return self

    def __sub__(self, other: int | UInt64) -> UInt64:
        """
        Subtract another UInt64 or int from the UInt64.

        Args:
            other (int | UInt64): The object to subtract from the UInt64.

        Raises:
            UInt64UnderflowError: If the subtraction result is negative.

        Returns:
            UInt64: The result of the subtraction.
        """
        result = self.value - self._get_value(other)
        if result < 0:
            raise UInt64UnderflowError(result)
        return UInt64(result)

    def __rsub__(self, other: int) -> UInt64:
        """
        Subtract the UInt64 from an int.

        Args:
            other (int): The int to subtract the UInt64 from.

        Raises:
            UInt64UnderflowError: If the subtraction result is negative.

        Returns:
            UInt64: The result of the subtraction.
        """
        result = other - self.value
        if result < 0:
            raise UInt64UnderflowError(result)
        return UInt64(result)

    def __isub__(self, other: int | UInt64) -> Self:
        """
        In-place subtraction of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to subtract from the UInt64.

        Raises:
            UInt64UnderflowError: If the subtraction result is negative.

        Returns:
            Self: The result of the in-place subtraction.
        """
        result = self.value - self._get_value(other)
        if result < 0:
            raise UInt64UnderflowError(result)
        self.value = result
        return self

    def __mul__(self, other: int | UInt64) -> UInt64:
        """
        Multiply the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The object to multiply the UInt64 by.

        Raises:
            UInt64OverflowError: If the multiplication result exceeds the
            maximum value for a UInt64

        Returns:
            UInt64: The result of the multiplication.
        """
        result = self.value * self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        return UInt64(result)

    def __rmul__(self, other: int) -> UInt64:
        """
        Multiply the UInt64 by an int.

        Args:
            other (int): The int to multiply the UInt64 by.

        Returns:
            UInt64: The result of the multiplication.
        """
        return self.__mul__(other)

    def __imul__(self, other: int | UInt64) -> Self:
        """
        In-place multiplication of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to multiply the UInt64 by.

        Raises:
            UInt64OverflowError: If the multiplication result
            exceeds the maximum value for a UInt64.

        Returns:
            Self: The result of the in-place multiplication.
        """
        result = self.value * self._get_value(other)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        self.value = result
        return self

    def __floordiv__(self, other: int | UInt64) -> UInt64:
        """
        Floor divide the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The object to divide the UInt64 by.

        Raises:
            UInt64ZeroDivisionError: If the divisor is zero.

        Returns:
            UInt64: The result of the floor division.
        """
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        return UInt64(self.value // other_value)

    def __rfloordiv__(self, other: int) -> UInt64:
        """
        Floor divide an int by the UInt64.

        Args:
            other (int): The int to divide by the UInt64.

        Raises:
            UInt64ZeroDivisionError: If the UInt64 is zero.

        Returns:
            UInt64: The result of the floor division.
        """
        if self.value == 0:
            raise UInt64ZeroDivisionError(self.value)
        return UInt64(other // self.value)

    def __ifloordiv__(self, other: int | UInt64) -> Self:
        """
        In-place floor division of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to divide the UInt64 by.

        Raises:
            UInt64ZeroDivisionError: If the divisor is zero.

        Returns:
            Self: The result of the in-place floor division.
        """
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        self.value //= other_value
        return self

    def __mod__(self, other: int | UInt64) -> UInt64:
        """
        Compute the modulus of the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the modulus by.

        Raises:
            UInt64ZeroDivisionError: If the divisor is zero.

        Returns:
            UInt64: The result of the modulus operation.
        """
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        return UInt64(self.value % other_value)

    def __rmod__(self, other: int) -> UInt64:
        """
        Compute the modulus of an int by the UInt64.

        Args:
            other (int): The int to compute the modulus by the UInt64.

        Raises:
            UInt64ZeroDivisionError: If the UInt64 is zero.

        Returns:
            UInt64: The result of the modulus operation.
        """
        if self.value == 0:
            raise UInt64ZeroDivisionError(self.value)
        return UInt64(other % self.value)

    def __imod__(self, other: int | UInt64) -> Self:
        """
        In-place modulus of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the modulus by.

        Raises:
            UInt64ZeroDivisionError: If the divisor is zero.

        Returns:
            Self: The result of the in-place modulus operation.
        """
        other_value = self._get_value(other)
        if other_value == 0:
            raise UInt64ZeroDivisionError(other_value)
        self.value %= other_value
        return self

    def __pow__(self, other: int | UInt64, modulo: int | UInt64 | None = None) -> UInt64:
        """
        Raise the UInt64 to the power of another UInt64 or int.

        Args:
            other (int | UInt64): The exponent to raise the UInt64 to.
            modulo (int | UInt64 | None, optional): The modulus to apply to the result.
            Defaults to None.

        Raises:
            UInt64OverflowError: If the power result exceeds the maximum value for a UInt64.

        Returns:
            UInt64: The result of the power operation.
        """
        exp = self._get_value(other)
        if modulo is not None:
            mod = self._get_value(modulo)
            result = pow(self.value, exp, mod)
        else:
            result = pow(self.value, exp)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        return UInt64(result)

    def __rpow__(self, other: int) -> UInt64:
        """
        Raise an int to the power of the UInt64.

        Args:
            other (int): The base to raise to the power of the UInt64.

        Raises:
            UInt64OverflowError: If the power result exceeds the maximum value for a UInt64.

        Returns:
            UInt64: The result of the power operation.
        """
        result: int = pow(other, self.value)
        if result > MAX_UINT64:
            raise UInt64OverflowError(result)
        return UInt64(result)

    def __ipow__(self, other: int | UInt64, modulo: int | UInt64 | None = None) -> Self:
        """
        In-place power of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The exponent to raise the UInt64 to.
            modulo (int | UInt64 | None, optional): The modulus to apply to the result.
            Defaults to None.

        Raises:
            OverflowError: If the power result exceeds the maximum value for a UInt64.

        Returns:
            Self: The result of the in-place power operation.
        """
        exp = self._get_value(other)
        self.value = pow(self.value, exp, MAX_UINT64 + 1)
        if self.value > MAX_UINT64:
            raise OverflowError("UInt64 power result exceeds maximum value")
        return self

    def __lshift__(self, other: int | UInt64) -> UInt64:
        """
        Left shift the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The amount to shift the UInt64 by.

        Raises:
            ValueError: If the shift amount is negative.

        Returns:
            UInt64: The result of the left shift operation.
        """
        shift = self._get_value(other)
        if shift < 0:
            raise UInt64BitShiftInvalidValueError("Shift amount must be non-negative")
        if shift >= 64:
            return UInt64(0)
        result = (self.value << shift) & MAX_UINT64
        return UInt64(result)

    def __rlshift__(self, other: int) -> UInt64:
        """
        Left shift an int by the UInt64.

        Args:
            other (int): The int to shift by the UInt64.

        Raises:
            ValueError: If the shift amount is negative or greater than 63.
            OverflowError: If the left shift result exceeds the maximum value for a UInt64.

        Returns:
            UInt64: The result of the left shift operation.
        """
        return self.__lshift__(other)

    def __ilshift__(self, other: int | UInt64) -> Self:
        """
        In-place left shift of the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The amount to shift the UInt64 by.

        Raises:
            ValueError: If the shift amount is negative or greater than 63.
            UInt64BitShiftOverflowError: If the left shift result exceeds
            the maximum value for a UInt64.

        Returns:
            Self: The result of the in-place left shift operation.
        """
        shift_amount = self._get_value(other)
        if shift_amount < 0 or shift_amount > MAX_UINT64_BIT_SHIFT:
            raise UInt64BitShiftInvalidValueError(
                "Shift amount must be between 0 and 63",
            )
        self.value <<= shift_amount
        if self.value > MAX_UINT64:
            raise UInt64BitShiftOverflowError(self.value, shift_amount)
        return self

    def __rshift__(self, other: int | UInt64) -> UInt64:
        """
        Right shift the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The amount to shift the UInt64 by.

        Raises:
            ValueError: If the shift amount is negative or greater than 63.

        Returns:
            UInt64: The result of the right shift operation.
        """
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise UInt64BitShiftInvalidValueError(
                "Shift amount must be between 0 and 63",
            )
        return UInt64(self.value >> shift)

    def __rrshift__(self, other: int) -> UInt64:
        """
        Right shift an int by the UInt64.

        Args:
            other (int): The int to shift by the UInt64.

        Raises:
            ValueError: If the shift amount is negative or greater than 63.

        Returns:
            UInt64: The result of the right shift operation.
        """
        return self.__rshift__(other)

    def __irshift__(self, other: int | UInt64) -> Self:
        """
        In-place right shift of the UInt64 by another UInt64 or int.

        Args:
            other (int | UInt64): The amount to shift the UInt64 by.

        Raises:
            ValueError: If the shift amount is negative or greater than 63.

        Returns:
            Self: The result of the in-place right shift operation.
        """
        shift = self._get_value(other)
        if shift < 0 or shift > MAX_UINT64_BIT_SHIFT:
            raise UInt64BitShiftInvalidValueError("Shift amount must be between 0 and 63")
        self.value >>= shift
        return self

    def __and__(self, other: int | UInt64) -> UInt64:
        """
        Compute the bitwise AND of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise AND with.

        Returns:
            UInt64: The result of the bitwise AND operation.
        """
        return UInt64(self.value & self._get_value(other))

    def __rand__(self, other: int) -> UInt64:
        """
        Compute the bitwise AND of an int with the UInt64.

        Args:
            other (int): The int to compute the bitwise AND with.

        Returns:
            UInt64: The result of the bitwise AND operation.
        """
        return self.__and__(other)

    def __iand__(self, other: int | UInt64) -> Self:
        """
        In-place bitwise AND of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise AND with.

        Returns:
            Self: The result of the in-place bitwise AND operation.
        """
        self.value &= self._get_value(other)
        return self

    def __or__(self, other: int | UInt64) -> UInt64:
        """
        Compute the bitwise OR of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise OR with.

        Returns:
            UInt64: The result of the bitwise OR operation.
        """
        return UInt64(self.value | self._get_value(other))

    def __ror__(self, other: int) -> UInt64:
        """
        Compute the bitwise OR of an int with the UInt64.

        Args:
            other (int): The int to compute the bitwise OR with.

        Returns:
            UInt64: The result of the bitwise OR operation.
        """
        return self.__or__(other)

    def __ior__(self, other: int | UInt64) -> Self:
        """
        In-place bitwise OR of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise OR with.

        Returns:
            Self: The result of the in-place bitwise OR operation.
        """
        self.value |= self._get_value(other)
        return self

    def __xor__(self, other: int | UInt64) -> UInt64:
        """
        Compute the bitwise XOR of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise XOR with.

        Returns:
            UInt64: The result of the bitwise XOR operation.
        """
        return UInt64(self.value ^ self._get_value(other))

    def __rxor__(self, other: int) -> UInt64:
        """
        Compute the bitwise XOR of an int with the UInt64.

        Args:
            other (int): The int to compute the bitwise XOR with.

        Returns:
            UInt64: The result of the bitwise XOR operation.
        """
        return self.__xor__(other)

    def __ixor__(self, other: int | UInt64) -> Self:
        """
        In-place bitwise XOR of the UInt64 with another UInt64 or int.

        Args:
            other (int | UInt64): The object to compute the bitwise XOR with.

        Returns:
            Self: The result of the in-place bitwise XOR operation.
        """
        self.value ^= self._get_value(other)
        return self

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

        return UInt64(+self.value)
