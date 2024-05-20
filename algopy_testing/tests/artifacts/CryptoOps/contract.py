from algopy import ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4, ensure_budget, op


class CryptoOpsContract(ARC4Contract):
    @arc4.abimethod()
    def verify_sha256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        a = op.bzero(pad_size) + a
        result = op.sha256(a)
        return result

    @arc4.abimethod()
    def verify_sha3_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        a = op.bzero(pad_size) + a
        result = op.sha3_256(a)
        return result

    @arc4.abimethod()
    def verify_keccak_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        a = op.bzero(pad_size) + a
        result = op.keccak256(a)
        return result

    @arc4.abimethod()
    def verify_sha512_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        a = op.bzero(pad_size) + a
        result = op.sha512_256(a)
        return result

    @arc4.abimethod()
    def verify_ed25519verify(self, a: Bytes, b: Bytes, c: Bytes) -> arc4.Bool:
        ensure_budget(1900, OpUpFeeSource.GroupCredit)
        result = op.ed25519verify(a, b, c)
        return arc4.Bool(result)

    @arc4.abimethod()
    def verify_ed25519verify_bare(self, a: Bytes, b: Bytes, c: Bytes) -> arc4.Bool:
        ensure_budget(1900, OpUpFeeSource.GroupCredit)
        result = op.ed25519verify_bare(a, b, c)
        return arc4.Bool(result)

    @arc4.abimethod()
    def verify_ecdsa_verify_k1(  # noqa: PLR0913
        self, a: Bytes, b: Bytes, c: Bytes, d: Bytes, e: Bytes
    ) -> bool:
        ensure_budget(3000, OpUpFeeSource.GroupCredit)
        result_k1 = op.ecdsa_verify(op.ECDSA.Secp256k1, a, b, c, d, e)
        return result_k1

    @arc4.abimethod()
    def verify_ecdsa_verify_r1(  # noqa: PLR0913
        self, a: Bytes, b: Bytes, c: Bytes, d: Bytes, e: Bytes
    ) -> bool:
        ensure_budget(3000, OpUpFeeSource.GroupCredit)
        result_r1 = op.ecdsa_verify(op.ECDSA.Secp256r1, a, b, c, d, e)
        return result_r1

    @arc4.abimethod()
    def verify_ecdsa_recover_k1(
        self, a: Bytes, b: UInt64, c: Bytes, d: Bytes
    ) -> tuple[Bytes, Bytes]:
        ensure_budget(3000, OpUpFeeSource.GroupCredit)
        return op.ecdsa_pk_recover(op.ECDSA.Secp256k1, a, b, c, d)

    @arc4.abimethod()
    def verify_ecdsa_recover_r1(
        self, a: Bytes, b: UInt64, c: Bytes, d: Bytes
    ) -> tuple[Bytes, Bytes]:
        """
        Must fail, AVM does not support Secp256r1 for recover
        """
        ensure_budget(3000, OpUpFeeSource.GroupCredit)
        return op.ecdsa_pk_recover(op.ECDSA.Secp256r1, a, b, c, d)

    @arc4.abimethod()
    def verify_ecdsa_decompress_k1(self, a: Bytes) -> tuple[Bytes, Bytes]:
        ensure_budget(700, OpUpFeeSource.GroupCredit)
        return op.ecdsa_pk_decompress(op.ECDSA.Secp256k1, a)

    @arc4.abimethod()
    def verify_ecdsa_decompress_r1(self, a: Bytes) -> tuple[Bytes, Bytes]:
        ensure_budget(700, OpUpFeeSource.GroupCredit)
        return op.ecdsa_pk_decompress(op.ECDSA.Secp256r1, a)

    @arc4.abimethod()
    def verify_vrf_verify(self, a: Bytes, b: Bytes, c: Bytes) -> tuple[Bytes, bool]:
        ensure_budget(5700, OpUpFeeSource.GroupCredit)
        result = op.vrf_verify(op.VrfVerify.VrfAlgorand, a, b, c)
        return result
