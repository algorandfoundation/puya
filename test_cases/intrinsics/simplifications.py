from algopy import BigUInt, Bytes, UInt64, arc4, op


class Simplifications(arc4.ARC4Contract):
    @arc4.abimethod()
    def select_neq(self, x: UInt64) -> UInt64:
        # select(false=0, true=1, selector=x) with a non-bool selector
        # simplifies to (x != 0)
        return op.select_uint64(0, 1, x)

    @arc4.abimethod()
    def chained_extract(self, src: Bytes) -> UInt64:
        # extract_uint16(extract(src, 2, 0), 1) folds to extract_uint16(src, 3)
        middle = op.extract(src, 2, 0)
        return op.extract_uint16(middle, 1)

    @arc4.abimethod()
    def biguint_add_fold(self, x: BigUInt) -> BigUInt:
        # (x + 5) + 3 folds the two constants to x + 8
        return x + BigUInt(5) + 3

    @arc4.abimethod()
    def biguint_mul_fold(self, x: BigUInt) -> BigUInt:
        # (x * 5) * 3 folds the two constants to x * 15
        return x * BigUInt(5) * 3

    @arc4.abimethod()
    def biguint_add_no_fold(self, x: BigUInt, y: BigUInt, z: BigUInt) -> BigUInt:
        # (x + y) + z has no constant operands, so nothing folds
        return x + y + z

    @arc4.abimethod()
    def biguint_add_bytes_const(self, x: BigUInt) -> BigUInt:
        # the byte-constant operand resolves to a biguint via the byte path,
        # then folds with the 3 to x + 8
        return x + BigUInt.from_bytes(Bytes(b"\x05")) + 3

    @arc4.abimethod()
    def biguint_add_oversized(self, x: BigUInt) -> BigUInt:
        # the byte-encoded sum exceeds 64 bytes, leaving a runtime b+ that fails
        too_big = BigUInt(2**512 - 1) + 1
        return x + too_big + 3

    @arc4.abimethod()
    def biguint_add_double_oversized(self, x: BigUInt, y: BigUInt) -> BigUInt:
        # folding the two 512-bit constants yields a 513-bit biguint constant
        # that is too large to fold into the accumulator
        return x + BigUInt(2**512 - 1) + (2**512 - 1) + y
