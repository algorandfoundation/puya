"""Example 12: Event Logger

This example demonstrates ARC-28 event emission with arc4.emit().

Features:
- arc4.emit() with Struct instance — emit using a native Struct
- arc4.emit('Name', ...args) — emit using explicit event name + positional args
- arc4.emit('Name(type,...)', ...args) — emit with explicit ARC-28 signature in the name string
- Multiple events in a single call — demonstrates batching pattern

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import ARC4Contract, Struct, UInt64, arc4


class Swapped(Struct):
    """Typed event using native Struct.

    Event signature: "Swapped(uint64,uint64)"
    """

    a: UInt64
    b: UInt64


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
    def emit_arc4_struct(self, a: UInt64, b: UInt64) -> None:
        """Emit a Swapped event using a native Struct instance.

        ARC-28 prefix: "Swapped(uint64,uint64)"

        Args:
            a: first value (will appear second in event)
            b: second value (will appear first in event)
        """
        arc4.emit(Swapped(a=b, b=a))

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
        arc4.emit(Swapped(a=x, b=x))
        arc4.emit("ValueSet(uint64)", x)


# example: EVENT_LOGGER
