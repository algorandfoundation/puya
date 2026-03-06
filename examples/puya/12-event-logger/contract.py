"""Example 12: Event Logger

This example demonstrates ARC-28 event emission with arc4.emit().

Features:
- arc4.emit() with arc4.Struct instance — emit using an arc4.Struct with arc4-encoded fields
- arc4.emit() with native algopy.Struct instance — emit using a Struct with native fields
- arc4.emit('Name', ...args) — emit using explicit event name + positional args
- arc4.emit('Name(type,...)', ...args) — emit with explicit ARC-28 signature in the name string
- Multiple events in a single call — demonstrates batching pattern

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import ARC4Contract, Struct, UInt64, arc4


class Swapped(arc4.Struct):
    """Typed event using arc4.Struct — arc4-encoded fields.

    Event signature: "Swapped(uint64,uint64)"
    """

    a: arc4.UInt64
    b: arc4.UInt64


class SwappedNative(Struct):
    """Typed event using native algopy.Struct — native uint64 fields.

    Event signature: "SwappedNative(uint64,uint64)"
    """

    a: UInt64
    b: UInt64


# example: EVENT_LOGGER
class EventLogger(ARC4Contract):
    """ARC-28 event logger contract demonstrating multiple emit patterns."""

    @arc4.abimethod
    def emit_arc4_struct(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        """Emit a Swapped event using an arc4.Struct instance with arc4-encoded values.

        ARC-28 prefix: "Swapped(uint64,uint64)"

        Args:
            a: first value (will appear second in event)
            b: second value (will appear first in event)
        """
        arc4.emit(Swapped(b, a))

    @arc4.abimethod
    def emit_native_struct(self, a: UInt64, b: UInt64) -> None:
        """Emit a SwappedNative event using a native algopy.Struct instance.

        ARC-28 prefix: "SwappedNative(uint64,uint64)"

        Args:
            a: first value (will appear second in event)
            b: second value (will appear first in event)
        """
        arc4.emit(SwappedNative(a=b, b=a))

    @arc4.abimethod
    def emit_by_name(self, a: UInt64, b: UInt64) -> None:
        """Emit a Swapped event by name — signature inferred from arg types.

        ARC-28 prefix: "Swapped(uint64,uint64)"

        Args:
            a: first value (will appear second in event)
            b: second value (will appear first in event)
        """
        arc4.emit("Swapped", b, a)

    @arc4.abimethod
    def emit_by_signature(self, a: UInt64, b: UInt64) -> None:
        """Emit a Swapped event with explicit ARC-28 signature string.

        ARC-28 prefix provided directly: "Swapped(uint64,uint64)"

        Args:
            a: first value (will appear second in event)
            b: second value (will appear first in event)
        """
        arc4.emit("Swapped(uint64,uint64)", b, a)

    @arc4.abimethod
    def emit_multiple(self, x: UInt64) -> None:
        """Emit multiple events in a single call — demonstrates batching pattern.

        Args:
            x: value used in both events
        """
        arc4.emit(Swapped(arc4.UInt64(x), arc4.UInt64(x)))
        arc4.emit("ValueSet(uint64)", x)


# example: EVENT_LOGGER
