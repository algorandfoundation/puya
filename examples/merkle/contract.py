import typing

from algopy import BigUInt, Bytes, arc4, op, subroutine, urange

Bytes32: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]
Proof: typing.TypeAlias = arc4.DynamicArray[Bytes32]


class MerkleTree(arc4.ARC4Contract):
    @arc4.abimethod(create=True)
    def create(self, root: Bytes32) -> None:
        self.root = root.bytes

    @arc4.abimethod
    def verify(self, proof: Proof, leaf: Bytes32) -> bool:
        return self.root == compute_root_hash(proof, leaf.bytes)


@subroutine
def compute_root_hash(proof: Proof, leaf: Bytes) -> Bytes:
    computed = leaf
    for idx in urange(proof.length):
        computed = hash_pair(computed, proof[idx].bytes)
    return computed


@subroutine
def hash_pair(a: Bytes, b: Bytes) -> Bytes:
    return op.sha256(a + b if BigUInt.from_bytes(a) < BigUInt.from_bytes(b) else b + a)
