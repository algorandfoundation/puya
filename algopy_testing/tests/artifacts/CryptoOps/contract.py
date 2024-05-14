from algopy import ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4, ensure_budget, op


class CryptoOpsContract(ARC4Contract):
    @arc4.abimethod()
    def verify_sha256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        ensure_budget(35, OpUpFeeSource.GroupCredit)
        a = op.bzero(pad_size) + a
        result = op.sha256(a)
        return result

    @arc4.abimethod()
    def verify_sha3_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        ensure_budget(130, OpUpFeeSource.GroupCredit)
        a = op.bzero(pad_size) + a
        result = op.sha3_256(a)
        return result

    @arc4.abimethod()
    def verify_keccak_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        ensure_budget(130, OpUpFeeSource.GroupCredit)
        a = op.bzero(pad_size) + a
        result = op.keccak256(a)
        return result

    @arc4.abimethod()
    def verify_sha512_256(self, a: Bytes, pad_size: UInt64) -> Bytes:
        ensure_budget(45, OpUpFeeSource.GroupCredit)
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
    def verify_ecdsa_verify(self, hash_value: Bytes, signature: Bytes) -> bool:
        ensure_budget(1700 + 2000, OpUpFeeSource.GroupCredit)
        r = signature[0:32]
        s = signature[32:64]
        v = op.btoi(signature[64:65]) - 27
        pk_tuple = op.ecdsa_pk_recover(op.ECDSA.Secp256k1, hash_value, v, r, s)
        return op.ecdsa_verify(op.ECDSA.Secp256k1, hash_value, r, s, pk_tuple[0], pk_tuple[1])

    @arc4.abimethod()
    def verify_ecdsa_recover(self, hash_value: Bytes, signature: Bytes) -> tuple[Bytes, Bytes]:
        ensure_budget(3000, OpUpFeeSource.GroupCredit)
        r = signature[0:32]
        s = signature[32:64]
        v = op.btoi(signature[64:65]) - 27
        return op.ecdsa_pk_recover(op.ECDSA.Secp256k1, hash_value, v, r, s)

    @arc4.abimethod()
    def verify_ecdsa_decompress(self, compressed_pk: Bytes) -> tuple[Bytes, Bytes]:
        ensure_budget(700, OpUpFeeSource.GroupCredit)
        return op.ecdsa_pk_decompress(op.ECDSA.Secp256k1, compressed_pk)
