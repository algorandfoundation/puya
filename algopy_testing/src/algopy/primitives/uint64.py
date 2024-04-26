# algopy_testing/src/algopy/primitives/uint64.py

from __future__ import annotations
from typing import Union, overload

from algopy.error.uint64 import UInt64UnderflowError, UInt64OverflowError
from algopy.primitives.constants import MAX_UINT64, MAX_UINT64_BIT_SHIFT

class UInt64(int):
    """
    A 64-bit unsigned integer, one of the primary data types on the AVM.
    """

    def __new__(cls, value: Union[int, 'UInt64'] = 0) -> 'UInt64':
        """
        Initialize a UInt64 instance with a given value or default to 0.
        """
        if not isinstance(value, (int, UInt64)):
            raise TypeError(f"Value must be an integer or UInt64, not {type(value)}")
        if value < 0:
            raise UInt64UnderflowError(value)
        elif value > MAX_UINT64:
            raise UInt64OverflowError(value)
        return super().__new__(cls, value)

    @overload
    def __add__(self, other: 'UInt64') -> 'UInt64': ...
    @overload
    def __add__(self, other: int) -> 'UInt64': ...

    def __add__(self, other):
        """
        Add this UInt64 instance to another UInt64 or int.
        """
        result = super().__add__(other)
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 addition result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __sub__(self, other):
        """
        Subtract another UInt64 or int from this UInt64 instance.
        """
        result = super().__sub__(other)
        if result < 0:
            raise ValueError(f"UInt64 subtraction result is negative: {result}")
        return UInt64(result)

    def __rsub__(self, other):
        """
        Subtract this UInt64 instance from another UInt64 or int.
        """
        result = other - self
        if result < 0:
            raise ValueError(f"UInt64 subtraction result is negative: {result}")
        return UInt64(result)

    def __mul__(self, other):
        """
        Multiply this UInt64 instance with another UInt64 or int.
        """
        result = super().__mul__(other)
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 multiplication result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __rmul__(self, other):
        """
        Multiply another UInt64 or int with this UInt64 instance.
        """
        return self.__mul__(other)
    
    def __floordiv__(self, other):
        """
        Floor divide this UInt64 instance by another UInt64 or int.
        """
        if other == 0:
            raise ZeroDivisionError("UInt64 division by zero")
        return UInt64(super().__floordiv__(other))

    def __rfloordiv__(self, other):
        """
        Floor divide another UInt64 or int by this UInt64 instance.
        """
        if self == 0:
            raise ZeroDivisionError("UInt64 division by zero")
        return UInt64(other // self)

    def __mod__(self, other):
        """
        Modulo this UInt64 instance by another UInt64 or int.
        """
        if other == 0:
            raise ZeroDivisionError("UInt64 modulo by zero")
        return UInt64(super().__mod__(other))

    def __rmod__(self, other):
        """
        Modulo another UInt64 or int by this UInt64 instance.
        """
        if self == 0:
            raise ZeroDivisionError("UInt64 modulo by zero")
        return UInt64(other % self)

    def __pow__(self, power):
        """
        Raise this UInt64 instance to the power of another UInt64 or int.
        """
        result = super().__pow__(power)
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 power result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __rpow__(self, other):
        """
        Raise another UInt64 or int to the power of this UInt64 instance.
        """
        result = other ** self
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 power result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __lshift__(self, other):
        """
        Left shift this UInt64 instance by another UInt64 or int.
        """
        if other >= MAX_UINT64_BIT_SHIFT:
            raise ValueError(f"UInt64 left shift amount exceeds maximum shift value: {MAX_UINT64_BIT_SHIFT}")
        
        result = super().__lshift__(other)
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 left shift result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __rlshift__(self, other):
        """
        Left shift another UInt64 or int by this UInt64 instance.
        """
        result = UInt64(other) << self
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 left shift result exceeds maximum value: {MAX_UINT64}")
        return result


    def __rshift__(self, other):
        """
        Right shift this UInt64 instance by another UInt64 or int.
        """
        result = super().__rshift__(other)
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 right shift result exceeds maximum value: {MAX_UINT64}")
        return UInt64(result)

    def __rrshift__(self, other):
        """
        Right shift another UInt64 or int by this UInt64 instance.
        """
        result = UInt64(other) >> self
        if result > MAX_UINT64:
            raise OverflowError(f"UInt64 right shift result exceeds maximum value: {MAX_UINT64}")
        return result

    def __and__(self, other):
        """
        Bitwise AND this UInt64 instance with another UInt64 or int.
        """
        return UInt64(super().__and__(other))

    def __rand__(self, other):
        """
        Bitwise AND another UInt64 or int with this UInt64 instance.
        """
        return UInt64(other) & self

    def __xor__(self, other):
        """
        Bitwise XOR this UInt64 instance with another UInt64 or int.
        """
        return UInt64(super().__xor__(other))

    def __rxor__(self, other):
        """
        Bitwise XOR another UInt64 or int with this UInt64 instance.
        """
        return UInt64(other) ^ self

    def __or__(self, other):
        """
        Bitwise OR this UInt64 instance with another UInt64 or int.
        """
        return UInt64(super().__or__(other))

    def __ror__(self, other):
        """
        Bitwise OR another UInt64 or int with this UInt64 instance.
        """
        return UInt64(other) | self

    def __invert__(self):
        """
        Bitwise invert this UInt64 instance.
        """
        return UInt64(super().__invert__() & MAX_UINT64)

    def __repr__(self) -> str:
        return f"UInt64({super().__repr__()})"
