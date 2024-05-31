from algopy import ARC4Contract, BigUInt, Bytes, arc4


class Arc4PrimitiveOpsContract(ARC4Contract):
    @arc4.abimethod()
    def verify_uintn_uintn_eq(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) == arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_eq(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) == arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_eq(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) == arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_eq(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) == arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_uintn_ne(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) != arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_ne(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) != arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_ne(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) != arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_ne(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) != arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_uintn_lt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) < arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_lt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) < arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_lt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) < arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_lt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) < arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_uintn_le(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) <= arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_le(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) <= arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_le(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) <= arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_le(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) <= arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_uintn_gt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) > arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_gt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) > arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_gt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) > arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_gt(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) > arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_uintn_ge(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) >= arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_uintn_ge(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) >= arc4.UInt64(b_biguint)

    @arc4.abimethod()
    def verify_uintn_biguintn_ge(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt64(a_biguint) >= arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_biguintn_biguintn_ge(self, a: Bytes, b: Bytes) -> bool:
        a_biguint = BigUInt.from_bytes(a)
        b_biguint = BigUInt.from_bytes(b)
        return arc4.UInt512(a_biguint) >= arc4.UInt512(b_biguint)

    @arc4.abimethod()
    def verify_uintn_init(self, a: Bytes) -> arc4.UInt32:
        a_biguint = BigUInt.from_bytes(a)
        return arc4.UInt32(a_biguint)

    @arc4.abimethod()
    def verify_biguintn_init(self, a: Bytes) -> arc4.UInt256:
        a_biguint = BigUInt.from_bytes(a)
        return arc4.UInt256(a_biguint)

    @arc4.abimethod()
    def verify_uintn_from_log(self, a: Bytes) -> arc4.UInt32:
        return arc4.UInt32.from_log(a)

    @arc4.abimethod()
    def verify_biguintn_from_log(self, a: Bytes) -> arc4.UInt256:
        return arc4.UInt256.from_log(a)
