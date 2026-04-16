import typing

from algopy import ARC4Contract, Struct, UInt64, arc4


class Swapped(arc4.Struct):
    """This is a docstring for Swapped"""

    a: arc4.UInt64
    b: arc4.UInt64
    """These are field docs for Swapped.b"""


class NativeSwapped(Struct):
    """This is a docstring for NativeSwapped"""

    a: UInt64
    "These are field docs for NativeSwapped.a"
    b: UInt64


class EventEmitter(ARC4Contract):
    @arc4.abimethod
    def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        arc4.emit(Swapped(b, a))
        arc4.emit("Swapped(uint64,uint64)", b, a)
        arc4.emit("Swapped", b, a)

    @arc4.abimethod
    def emit_native_swapped(self, a: UInt64, b: UInt64) -> None:
        arc4.emit(NativeSwapped(a=b, b=a))

    @arc4.abimethod()
    def emit_ufixed(
        self,
        a: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]],
        b: arc4.UFixedNxM[typing.Literal[64], typing.Literal[2]],
    ) -> None:
        arc4.emit("AnEvent(ufixed256x16,ufixed64x2)", a, b)
