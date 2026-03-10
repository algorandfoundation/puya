"""
Example 04: Type Explorer

This example demonstrates uint64, biguint, and bytes primitive types
with AVM opcodes for type conversions and wide math.

Features:
- uint64 / biguint / bytes primitive types and conversions
- UInt64, BigUInt, Bytes factory types
- op.itob() uint64 -> bytes conversion
- op.btoi() bytes -> uint64 conversion
- op.addw() 128-bit addition
- op.mulw() 128-bit multiplication

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import ARC4Contract, Bytes, UInt64, arc4, op


# example: TYPE_EXPLORER
class TypeExplorer(ARC4Contract):
    """Type explorer contract showcasing primitive types, conversions, and low-level ops."""

    @arc4.abimethod
    def uint64_add(self, a: UInt64, b: UInt64) -> UInt64:
        """Add two uint64 values.

        Args:
            a: First uint64 operand.
            b: Second uint64 operand.

        Returns:
            The sum of a and b.
        """
        return a + b

    @arc4.abimethod
    def uint64_pow(self, base: UInt64, exp: UInt64) -> UInt64:
        """Raise a uint64 base to a uint64 exponent.

        Args:
            base: Base value.
            exp: Exponent value.

        Returns:
            base raised to the power of exp.
        """
        return base**exp

    @arc4.abimethod
    def biguint_add(self, a: arc4.UInt512, b: arc4.UInt512) -> arc4.UInt512:
        """Add two biguint values via arc4.UInt512.

        Args:
            a: First biguint operand.
            b: Second biguint operand.

        Returns:
            The sum as arc4.UInt512.
        """
        result = a.as_biguint() + b.as_biguint()
        return arc4.UInt512(result)

    @arc4.abimethod
    def biguint_mul(self, a: arc4.UInt512, b: arc4.UInt512) -> arc4.UInt512:
        """Multiply two biguint values via arc4.UInt512.

        Args:
            a: First biguint operand.
            b: Second biguint operand.

        Returns:
            The product as arc4.UInt512.
        """
        result = a.as_biguint() * b.as_biguint()
        return arc4.UInt512(result)

    @arc4.abimethod
    def bytes_len(self, data: Bytes) -> UInt64:
        """Return the length of a bytes value.

        Args:
            data: Arbitrary bytes.

        Returns:
            Length of data in bytes.
        """
        return data.length

    @arc4.abimethod
    def itob_convert(self, value: UInt64) -> Bytes:
        """Convert uint64 to big-endian bytes via op.itob.

        Args:
            value: uint64 value to convert.

        Returns:
            8-byte big-endian representation.
        """
        return op.itob(value)

    @arc4.abimethod
    def btoi_convert(self, value: Bytes) -> UInt64:
        """Convert big-endian bytes to uint64 via op.btoi.

        Args:
            value: Big-endian bytes to convert.

        Returns:
            The uint64 value.
        """
        return op.btoi(value)

    @arc4.abimethod
    def wide_add(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        """128-bit addition via op.addw, returning carry and low.

        Args:
            a: First uint64 operand.
            b: Second uint64 operand.

        Returns:
            Tuple of (carry, low) representing the 128-bit sum.
        """
        carry, low = op.addw(a, b)
        return carry, low

    @arc4.abimethod
    def wide_multiply(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        """128-bit multiplication via op.mulw, returning high and low.

        Args:
            a: First uint64 operand.
            b: Second uint64 operand.

        Returns:
            Tuple of (high, low) representing the 128-bit product.
        """
        high, low = op.mulw(a, b)
        return high, low


# example: TYPE_EXPLORER
