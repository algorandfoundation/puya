from algopy import Bytes, arc4, op


class Optimizations(arc4.ARC4Contract):
    @arc4.abimethod()
    def sha256(self) -> Bytes:
        return op.sha256(b"Hello World")
