from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class CryptoOps(ARC4Contract):
    """
    A tour of the cryptographic opcodes exposed via `algopy.op`.

    All hash and verify opcodes accept `BytesBacked` inputs: `Bytes`,
    `String`, `arc4` values, account addresses; basically any type that is
    represented as a byte array in the TEAL code (including plain `bytes`
    literals).

    Most of these opcodes are expensive: they cost far more than the 700
    opcode-budget units a single application call provides, so callers
    typically pool budget by grouping the call with extra app calls, or the
    contract raises its own budget with `algopy.ensure_budget` (see the
    op_budget example).

    As many of these constitute some sort of cryptographic verification,
    many times they can also be used in conjunction with logic signatures,
    which are stateless programs executed at transaction signature verification
    time but have a budget separate to app calls in a group.
    """

    # example: SHA_HASHES
    @arc4.abimethod
    def hashes(self, data: Bytes) -> tuple[Bytes, Bytes, Bytes, Bytes]:
        """
        Most common hashing algorithms.
        All return `Bytes`. Always remember that the input arguments
        are visible in the AVM, and thus the preimage of the hash
        is easily reconstructible for anything being hashed on-chain.
        """
        return (
            op.sha256(data),
            op.sha3_256(data),
            op.sha512_256(data),
            op.keccak256(data),
        )

    # example: SHA_HASHES

    # example: ED25519_VERIFY
    @arc4.abimethod
    def ed25519(self, data: Bytes, signature: Bytes, public_key: Bytes) -> tuple[bool, bool]:
        """
        Two ed25519 verify variants:
          * `ed25519verify` given some data, a signature and a public key,
            it verifies the signature over `"ProgData" || program_hash || data`
            (where `program_hash` is the hash of the current program and "ProgData"
            is just a string used as domain separator).
          * `ed25519verify_bare` given the same 3 parameters, it verifies
            the signature over the raw data.
        """
        bound = op.ed25519verify(data, signature, public_key)
        bare = op.ed25519verify_bare(data, signature, public_key)
        return bound, bare

    # example: ED25519_VERIFY

    # example: ECDSA_VERIFY
    @arc4.abimethod
    def ecdsa(
        self,
        data: Bytes,
        sig_r: Bytes,
        sig_s: Bytes,
        pubkey_x: Bytes,
        pubkey_y: Bytes,
    ) -> tuple[bool, bool]:
        """
        ECDSA verify over either Secp256k1 (Bitcoin-compatible) or
        Secp256r1 (used by passkeys / WebAuthn). `data` must be a 32-byte
        digest of the signed message (hash it before calling); the signature
        is supplied as (R, S) — in canonical low-S form — and the public key
        as (X, Y), both decompressed.
        """
        k1 = op.ecdsa_verify(op.ECDSA.Secp256k1, data, sig_r, sig_s, pubkey_x, pubkey_y)
        r1 = op.ecdsa_verify(op.ECDSA.Secp256r1, data, sig_r, sig_s, pubkey_x, pubkey_y)
        return k1, r1

    @arc4.abimethod
    def ecdsa_decompress(self, compressed_pubkey: Bytes) -> tuple[Bytes, Bytes]:
        """
        `ecdsa_pk_decompress` expands a compressed (33-byte) Secp256k1 or
        Secp256r1 public key into its (X, Y) components. Useful for
        accepting compressed keys on the wire while feeding `ecdsa_verify`.
        """
        return op.ecdsa_pk_decompress(op.ECDSA.Secp256k1, compressed_pubkey)

    @arc4.abimethod
    def ecdsa_recover(
        self, digest: Bytes, recovery_id: UInt64, sig_r: Bytes, sig_s: Bytes
    ) -> tuple[Bytes, Bytes]:
        """
        `ecdsa_pk_recover` recovers the signer's public key (X, Y) from a
        32-byte digest, a signature and its recovery id — Bitcoin/Ethereum
        style "ecrecover". Only supported for Secp256k1.
        """
        return op.ecdsa_pk_recover(op.ECDSA.Secp256k1, digest, recovery_id, sig_r, sig_s)

    # example: ECDSA_VERIFY

    # example: VRF_VERIFY
    @arc4.abimethod
    def vrf(self, message: Bytes, proof: Bytes, public_key: Bytes) -> tuple[Bytes, bool]:
        """
        VRF (Verifiable Random Function) verification using the
        `VrfAlgorand` parameter set (ECVRF-ED25519-SHA512-Elligator2).

        Returns a `(vrf_output, verified)` tuple: the output is the random
        bytes derived from the message, and `verified` is True only if the
        proof checks against `public_key`. The output is meaningful only
        when `verified` is True.
        """
        return op.vrf_verify(op.VrfVerify.VrfAlgorand, message, proof, public_key)

    # example: VRF_VERIFY
