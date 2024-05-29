from algopy import ARC4Contract, BigUInt, Bytes, UInt64, arc4, op


class MiscellaneousOpsContract(ARC4Contract):
    @arc4.abimethod()
    def verify_addw(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        result = op.addw(a, b)
        return result

    @arc4.abimethod()
    def verify_base64_decode_standard(self, a: Bytes) -> Bytes:
        result = op.base64_decode(op.Base64.StdEncoding, a)
        return result

    @arc4.abimethod()
    def verify_base64_decode_url(self, a: Bytes) -> Bytes:
        result = op.base64_decode(op.Base64.URLEncoding, a)
        return result

    @arc4.abimethod()
    def verify_bytes_bitlen(self, a: Bytes, pad_a_size: UInt64) -> UInt64:
        a = op.bzero(pad_a_size) + a
        result = op.bitlen(a)
        return result

    @arc4.abimethod()
    def verify_uint64_bitlen(self, a: UInt64) -> UInt64:
        result = op.bitlen(a)
        return result

    @arc4.abimethod()
    def verify_bsqrt(self, a: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = op.bsqrt(a_biguint)
        return result.bytes

    @arc4.abimethod()
    def verify_btoi(self, a: Bytes) -> UInt64:
        result = op.btoi(a)
        return result

    @arc4.abimethod()
    def verify_bzero(self, a: UInt64) -> Bytes:
        result = op.bzero(a)
        return op.sha256(result)

    @arc4.abimethod()
    def verify_concat(self, a: Bytes, b: Bytes, pad_a_size: UInt64, pad_b_size: UInt64) -> Bytes:
        a = op.bzero(pad_a_size) + a
        b = op.bzero(pad_b_size) + b
        result = a + b
        result = op.sha256(result)
        return result

    @arc4.abimethod()
    def verify_divmodw(
        self, a: UInt64, b: UInt64, c: UInt64, d: UInt64
    ) -> tuple[UInt64, UInt64, UInt64, UInt64]:
        result = op.divmodw(a, b, c, d)
        return result

    @arc4.abimethod()
    def verify_divw(self, a: UInt64, b: UInt64, c: UInt64) -> UInt64:
        result = op.divw(a, b, c)
        return result

    @arc4.abimethod()
    def verify_err(self) -> None:
        op.err()

    @arc4.abimethod()
    def verify_exp(self, a: UInt64, b: UInt64) -> UInt64:
        result = op.exp(a, b)
        return result

    @arc4.abimethod()
    def verify_expw(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        result = op.expw(a, b)
        return result

    @arc4.abimethod()
    def verify_extract(self, a: Bytes, b: UInt64, c: UInt64) -> Bytes:
        result = op.extract(a, b, c)
        return result

    @arc4.abimethod()
    def verify_extract_from_2(self, a: Bytes) -> Bytes:
        result = op.extract(a, 2, 0)
        return result

    @arc4.abimethod()
    def verify_extract_uint16(self, a: Bytes, b: UInt64) -> UInt64:
        result = op.extract_uint16(a, b)
        return result

    @arc4.abimethod()
    def verify_extract_uint32(self, a: Bytes, b: UInt64) -> UInt64:
        result = op.extract_uint32(a, b)
        return result

    @arc4.abimethod()
    def verify_extract_uint64(self, a: Bytes, b: UInt64) -> UInt64:
        result = op.extract_uint64(a, b)
        return result

    @arc4.abimethod()
    def verify_getbit_bytes(self, a: Bytes, b: UInt64) -> UInt64:
        result = op.getbit(a, b)
        return result

    @arc4.abimethod()
    def verify_getbit_uint64(self, a: UInt64, b: UInt64) -> UInt64:
        result = op.getbit(a, b)
        return result

    @arc4.abimethod()
    def verify_getbyte(self, a: Bytes, b: UInt64) -> UInt64:
        result = op.getbyte(a, b)
        return result

    @arc4.abimethod()
    def verify_itob(self, a: UInt64) -> Bytes:
        result = op.itob(a)
        return result

    @arc4.abimethod()
    def verify_mulw(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        result = op.mulw(a, b)
        return result

    @arc4.abimethod()
    def verify_replace(self, a: Bytes, b: UInt64, c: Bytes) -> Bytes:
        result = op.replace(a, b, c)
        return result

    @arc4.abimethod()
    def verify_select_bytes(self, a: Bytes, b: Bytes, c: UInt64) -> Bytes:
        result = op.select_bytes(a, b, c)
        return result

    @arc4.abimethod()
    def verify_select_uint64(self, a: UInt64, b: UInt64, c: UInt64) -> UInt64:
        result = op.select_uint64(a, b, c)
        return result

    @arc4.abimethod()
    def verify_setbit_bytes(self, a: Bytes, b: UInt64, c: UInt64) -> Bytes:
        result = op.setbit_bytes(a, b, c)
        return result

    @arc4.abimethod()
    def verify_setbit_uint64(self, a: UInt64, b: UInt64, c: UInt64) -> UInt64:
        result = op.setbit_uint64(a, b, c)
        return result

    @arc4.abimethod()
    def verify_setbyte(self, a: Bytes, b: UInt64, c: UInt64) -> Bytes:
        result = op.setbyte(a, b, c)
        return result

    @arc4.abimethod()
    def verify_shl(self, a: UInt64, b: UInt64) -> UInt64:
        result = op.shl(a, b)
        return result

    @arc4.abimethod()
    def verify_shr(self, a: UInt64, b: UInt64) -> UInt64:
        result = op.shr(a, b)
        return result

    @arc4.abimethod()
    def verify_sqrt(self, a: UInt64) -> UInt64:
        result = op.sqrt(a)
        return result

    @arc4.abimethod()
    def verify_substring(self, a: Bytes, b: UInt64, c: UInt64) -> Bytes:
        result = op.substring(a, b, c)
        return result

    @arc4.abimethod()
    def verify_json_ref_string(self, a: Bytes, b: Bytes) -> Bytes:
        result = op.JsonRef.json_string(a, b)
        return result

    @arc4.abimethod()
    def verify_json_ref_uint64(self, a: Bytes, b: Bytes) -> UInt64:
        result = op.JsonRef.json_uint64(a, b)
        return result

    @arc4.abimethod()
    def verify_json_ref_object(self, a: Bytes, b: Bytes) -> Bytes:
        result = op.JsonRef.json_object(a, b)
        return result
