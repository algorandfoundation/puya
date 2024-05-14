from algopy import ARC4Contract, Bytes, UInt64, arc4, op


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
    def verify_bytes_add(self, a: Bytes, b: Bytes, pad_a_size: UInt64, pad_b_size: UInt64) -> Bytes:
        a =  op.bzero(pad_a_size) + a
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
    def verify_bytes_not(self, a: Bytes) -> Bytes:
        result = ~a
        return result
