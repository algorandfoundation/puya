import typing

from algopy import ARC4Contract, arc4


class Swapped(arc4.Struct):
    a: arc4.UInt64
    b: arc4.UInt64


class EventEmitter(ARC4Contract):
    @arc4.abimethod
    def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        arc4.emit(Swapped(b, a))
        arc4.emit("Swapped(uint64,uint64)", b, a)
        arc4.emit("Swapped", b, a)

    @arc4.abimethod()
    def emit_ufixed(
        self,
        a: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]],
        b: arc4.UFixedNxM[typing.Literal[64], typing.Literal[2]],
    ) -> None:
        arc4.emit("AnEvent(ufixed256x16,ufixed64x2)", a, b)
