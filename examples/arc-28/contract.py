from puyapy import ARC4Contract, arc4


class Swapped(arc4.Struct):
    a: arc4.UInt64
    b: arc4.UInt64


class EventEmitter(ARC4Contract):
    @arc4.abimethod
    def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        arc4.emit(Swapped(b, a))
        arc4.emit("Swapped(uint64,uint64)", b, a)
        arc4.emit("Swapped", b, a)
