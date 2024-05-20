from algopy import ARC4Contract, BigUInt, Bytes, String, UInt64, arc4, op


class PrimitiveOpsContract(ARC4Contract):
    @arc4.abimethod()
    def verify_uint64_init(self, raw_value: Bytes) -> UInt64:
        result = op.btoi(raw_value)
        return result

    @arc4.abimethod()
    def verify_uint64_add(self, a: UInt64, b: UInt64) -> UInt64:
        result = a + b
        return result

    @arc4.abimethod()
    def verify_uint64_sub(self, a: UInt64, b: UInt64) -> UInt64:
        result = a - b
        return result

    @arc4.abimethod()
    def verify_uint64_mul(self, a: UInt64, b: UInt64) -> UInt64:
        result = a * b
        return result

    @arc4.abimethod()
    def verify_uint64_div(self, a: UInt64, b: UInt64) -> UInt64:
        result = a // b
        return result

    @arc4.abimethod()
    def verify_uint64_mod(self, a: UInt64, b: UInt64) -> UInt64:
        result = a % b
        return result

    @arc4.abimethod()
    def verify_uint64_and(self, a: UInt64, b: UInt64) -> UInt64:
        result = a & b
        return result

    @arc4.abimethod()
    def verify_uint64_or(self, a: UInt64, b: UInt64) -> UInt64:
        result = a | b
        return result

    @arc4.abimethod()
    def verify_uint64_xor(self, a: UInt64, b: UInt64) -> UInt64:
        result = a ^ b
        return result

    @arc4.abimethod()
    def verify_uint64_not(self, a: UInt64) -> UInt64:
        result = ~a
        return result

    @arc4.abimethod()
    def verify_uint64_lshift(self, a: UInt64, b: UInt64) -> UInt64:
        result = a << b
        return result

    @arc4.abimethod()
    def verify_uint64_rshift(self, a: UInt64, b: UInt64) -> UInt64:
        result = a >> b
        return result

    @arc4.abimethod()
    def verify_uint64_pow(self, a: UInt64, b: UInt64) -> UInt64:
        result = a**b
        return result

    @arc4.abimethod()
    def verify_uint64_eq(self, a: UInt64, b: UInt64) -> bool:
        result = a == b
        return result

    @arc4.abimethod()
    def verify_uint64_ne(self, a: UInt64, b: UInt64) -> bool:
        result = a != b
        return result

    @arc4.abimethod()
    def verify_uint64_lt(self, a: UInt64, b: UInt64) -> bool:
        result = a < b
        return result

    @arc4.abimethod()
    def verify_uint64_le(self, a: UInt64, b: UInt64) -> bool:
        result = a <= b
        return result

    @arc4.abimethod()
    def verify_uint64_gt(self, a: UInt64, b: UInt64) -> bool:
        result = a > b
        return result

    @arc4.abimethod()
    def verify_uint64_ge(self, a: UInt64, b: UInt64) -> bool:
        result = a >= b
        return result

    @arc4.abimethod()
    def verify_bytes_init(self, raw_value: UInt64) -> Bytes:
        result = op.itob(raw_value)
        return result

    @arc4.abimethod()
    def verify_bytes_add(
        self, a: Bytes, b: Bytes, pad_a_size: UInt64, pad_b_size: UInt64
    ) -> Bytes:
        a = op.bzero(pad_a_size) + a
        b = op.bzero(pad_b_size) + b
        result = a + b
        result = op.sha256(result)
        return result

    @arc4.abimethod()
    def verify_bytes_eq(self, a: Bytes, b: Bytes) -> bool:
        result = a == b
        return result

    @arc4.abimethod()
    def verify_bytes_ne(self, a: Bytes, b: Bytes) -> bool:
        result = a != b
        return result

    @arc4.abimethod()
    def verify_bytes_and(self, a: Bytes, b: Bytes) -> Bytes:
        result = a & b
        return result

    @arc4.abimethod()
    def verify_bytes_or(self, a: Bytes, b: Bytes) -> Bytes:
        result = a | b
        return result

    @arc4.abimethod()
    def verify_bytes_xor(self, a: Bytes, b: Bytes) -> Bytes:
        result = a ^ b
        return result

    @arc4.abimethod()
    def verify_bytes_not(self, a: Bytes, pad_size: UInt64) -> Bytes:
        a = op.bzero(pad_size) + a
        result = ~a
        result = op.sha256(result)
        return result

    @arc4.abimethod()
    def verify_biguint_add(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint + b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_add_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint + b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_sub(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint - b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_sub_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint - b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_mul(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint * b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_mul_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint * b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_div(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint // b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_div_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint // b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_mod(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint % b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_mod_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint % b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_and(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint & b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_and_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint & b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_or(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint | b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_or_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint | b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_xor(self, a: Bytes, b: Bytes) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint ^ b_biguint
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_xor_uint64(self, a: Bytes, b: UInt64) -> Bytes:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint ^ b
        return result.bytes

    @arc4.abimethod()
    def verify_biguint_eq(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint == b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_eq_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint == b
        return result

    @arc4.abimethod()
    def verify_biguint_ne(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint != b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_ne_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint != b
        return result

    @arc4.abimethod()
    def verify_biguint_lt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint < b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_lt_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint < b
        return result

    @arc4.abimethod()
    def verify_biguint_le(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint <= b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_le_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint <= b
        return result

    @arc4.abimethod()
    def verify_biguint_gt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint > b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_gt_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint > b
        return result

    @arc4.abimethod()
    def verify_biguint_ge(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        result = a_biguint >= b_biguint
        return result

    @arc4.abimethod()
    def verify_biguint_ge_uint64(self, a: Bytes, b: UInt64) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        result = a_biguint >= b
        return result

    @arc4.abimethod
    def verify_string_init(self, a: String) -> String:
        result = String("Hello, ") + a
        return result

    @arc4.abimethod
    def verify_string_startswith(self, a: String, b: String) -> bool:
        result = a.startswith(b)
        return result

    @arc4.abimethod
    def verify_string_endswith(self, a: String, b: String) -> bool:
        result = a.endswith(b)
        return result

    # TODO: resolve join issue
    # @arc4.abimethod
    # def verify_string_join(self, a: String, b: String) -> String:
    #     result = String(", ").join((a, b))
    #     return result
