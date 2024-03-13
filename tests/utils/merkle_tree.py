import hashlib
import itertools


def sha_256_raw(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


class MerkleTree:
    def __init__(self, data: list[bytes]):
        self._tree = [[sha_256_raw(d) for d in data]]

        while len(self._tree[-1]) != 1:
            next_level = list[bytes]()
            for pair in itertools.batched(self._tree[-1], 2):
                (
                    a,
                    b,
                ) = (
                    pair if len(pair) == 2 else (pair[0], pair[0])
                )
                a_b_hash = self.hash_pair(a, b)
                next_level.append(a_b_hash)
            self._tree.append(next_level)

    @property
    def root(self) -> bytes:
        return self._tree[-1][0]

    @staticmethod
    def hash_pair(a: bytes, b: bytes) -> bytes:
        return sha_256_raw(a + b if a < b else b + a)

    def get_proof(self, data: bytes) -> list[bytes]:
        proof = list[bytes]()
        current = sha_256_raw(data)
        for level in self._tree:
            index = level.index(current)
            sibling_index = index - 1 if index % 2 == 1 else index + 1
            if sibling_index >= len(level):
                proof.append(current)
            else:
                proof.append(level[sibling_index])
            current = self.hash_pair(current, proof[-1])
        return proof[:-1]

    def verify_proof(self, data: bytes, proof: list[bytes]) -> bool:
        result = sha_256_raw(data)
        for item in proof:
            result = self.hash_pair(result, item)
        return result == self.root

    def __repr__(self) -> str:
        return "\n".join([str(level) for level in self._tree])
