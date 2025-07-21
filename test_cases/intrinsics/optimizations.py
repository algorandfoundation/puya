from algopy import Bytes, arc4, op


class Optimizations(arc4.ARC4Contract):
    @arc4.abimethod()
    def sha256(self) -> Bytes:
        return op.sha256(b"Hello World")

    @arc4.abimethod()
    def sha3_256(self) -> Bytes:
        return op.sha3_256(b"Hello World")

    @arc4.abimethod()
    def sha512_256(self) -> Bytes:
        return op.sha512_256(b"Hello World")

    @arc4.abimethod()
    def keccak256(self) -> Bytes:
        return op.keccak256(b"Hello World")

    @arc4.abimethod()
    def all(self, value_to_hash: Bytes) -> tuple[Bytes, Bytes, Bytes, Bytes]:
        return (
            op.sha256(value_to_hash),
            op.sha3_256(value_to_hash),
            op.sha512_256(value_to_hash),
            op.keccak256(value_to_hash),
        )
