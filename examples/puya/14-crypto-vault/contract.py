"""Example 14: Crypto Vault

This example demonstrates hash functions, signature verification, and scratch space.

Features:
- Hash functions (op.sha256, op.sha3_256, op.sha512_256, op.keccak256)
- Signature verification (op.ed25519verify_bare)
- Scratch space (op.Scratch.store, op.Scratch.load_bytes, op.Scratch.load_uint64)
- Contract options (scratch_slots reserves slots for manual use)
- AVM version set via avm_version on class

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

import algopy
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class CryptoVault(ARC4Contract, scratch_slots=[0, 1]):
    """Demonstrates hash functions, Ed25519 verification, and scratch space."""

    @arc4.abimethod()
    def hash_sha256(self, data: Bytes) -> Bytes:
        """Compute SHA-256 hash of data.

        Args:
            data: the input data to hash

        Returns:
            the 32-byte SHA-256 digest
        """
        return op.sha256(data)

    @arc4.abimethod()
    def hash_sha3_256(self, data: Bytes) -> Bytes:
        """Compute SHA3-256 hash of data.

        Args:
            data: the input data to hash

        Returns:
            the 32-byte SHA3-256 digest
        """
        return op.sha3_256(data)

    @arc4.abimethod()
    def hash_sha512_256(self, data: Bytes) -> Bytes:
        """Compute SHA-512/256 hash of data.

        Args:
            data: the input data to hash

        Returns:
            the 32-byte SHA-512/256 digest
        """
        return op.sha512_256(data)

    @arc4.abimethod()
    def hash_keccak256(self, data: Bytes) -> Bytes:
        """Compute Keccak-256 hash of data.

        Args:
            data: the input data to hash

        Returns:
            the 32-byte Keccak-256 digest
        """
        return op.keccak256(data)

    @arc4.abimethod()
    def verify_ed25519(
        self, data: Bytes, signature: Bytes, public_key: Bytes
    ) -> bool:
        """Verify an Ed25519 signature over data (bare, no program hash prefix).

        Args:
            data: the original message that was signed
            signature: the 64-byte Ed25519 signature
            public_key: the 32-byte Ed25519 public key

        Returns:
            True if the signature is valid
        """
        return op.ed25519verify_bare(data, signature, public_key)

    @arc4.abimethod()
    def scratch_store_and_load(self, value_uint: UInt64, value_bytes: Bytes) -> bool:
        """Store values in reserved scratch slots and load them back.

        Args:
            value_uint: the uint64 value to store in scratch slot 0
            value_bytes: the bytes value to store in scratch slot 1

        Returns:
            True if loaded values match the stored values
        """
        op.Scratch.store(0, value_uint)
        op.Scratch.store(1, value_bytes)

        loaded_uint = op.Scratch.load_uint64(0)
        loaded_bytes = op.Scratch.load_bytes(1)

        return loaded_uint == value_uint and loaded_bytes == value_bytes
