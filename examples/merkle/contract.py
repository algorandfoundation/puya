import typing

from algopy import (
    BigUInt,
    arc4,
    op,
    subroutine,
)

Bytes32: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]
Proof: typing.TypeAlias = arc4.DynamicArray[Bytes32]


class MerkleTree(arc4.ARC4Contract):
    @subroutine
    def hash_pair(self, a: Bytes32, b: Bytes32) -> Bytes32:
        hash_bytes = op.sha256(
            a.bytes + b.bytes
            if BigUInt.from_bytes(a.bytes) < BigUInt.from_bytes(b.bytes)
            else b.bytes + a.bytes
        )
        return Bytes32.from_bytes(hash_bytes)

    @subroutine
    def compute_root_hash(self, proof: Proof, leaf: Bytes32) -> Bytes32:
        computed = leaf.copy()
        for proof_hash in proof:
            computed = self.hash_pair(computed, proof_hash)
        return computed

    @arc4.abimethod(create=True)
    def create(self, root: Bytes32) -> None:
        self.root = root.copy()

    @arc4.abimethod
    def verify(self, proof: Proof, leaf: Bytes32) -> bool:
        return self.root == self.compute_root_hash(proof, leaf)
