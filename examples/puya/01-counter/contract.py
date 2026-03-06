"""
Example 01: Counter

This example demonstrates GlobalState and uint64 arithmetic.

Features:
- GlobalState (UInt64)
- uint64 arithmetic (+=, -=, *=, //=)
- compound assignment operators
- Uint64() factory for constants

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import ARC4Contract, UInt64, arc4


# example: COUNTER
class Counter(ARC4Contract):
    """Minimal counter contract demonstrating uint64 global state and ABI methods."""

    def __init__(self) -> None:
        """Initialise counter to zero using Uint64() factory."""
        self.counter = UInt64(0)

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Called once when the app is first deployed."""

    @arc4.abimethod
    def increment(self) -> UInt64:
        """Increment the counter by 1 using compound assignment (+=).

        Returns:
            Updated counter value.
        """
        self.counter += 1
        return self.counter

    @arc4.abimethod
    def decrement(self) -> UInt64:
        """Decrement the counter by 1 using compound assignment (-=).

        Returns:
            Updated counter value.
        """
        self.counter -= 1
        return self.counter

    @arc4.abimethod
    def multiply(self, factor: UInt64) -> UInt64:
        """Multiply the counter by the given factor using compound assignment (*=).

        Args:
            factor: Multiplier.

        Returns:
            Updated counter value.
        """
        self.counter *= factor
        return self.counter

    @arc4.abimethod
    def divide(self, divisor: UInt64) -> UInt64:
        """Divide the counter by the given divisor using compound assignment (//=).

        Args:
            divisor: Divisor.

        Returns:
            Updated counter value.
        """
        self.counter //= divisor
        return self.counter


# example: COUNTER
