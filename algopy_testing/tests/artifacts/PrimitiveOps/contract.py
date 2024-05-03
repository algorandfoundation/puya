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
