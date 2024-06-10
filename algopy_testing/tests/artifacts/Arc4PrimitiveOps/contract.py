import typing

from algopy import ARC4Contract, BigUInt, Bytes, String, arc4


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
    def verify_uintn_from_bytes(self, a: Bytes) -> arc4.UInt32:
        return arc4.UInt32.from_bytes(a)

    @arc4.abimethod()
    def verify_biguintn_from_bytes(self, a: Bytes) -> arc4.UInt256:
        return arc4.UInt256.from_bytes(a)

    @arc4.abimethod()
    def verify_uintn_from_log(self, a: Bytes) -> arc4.UInt32:
        return arc4.UInt32.from_log(a)

    @arc4.abimethod()
    def verify_biguintn_from_log(self, a: Bytes) -> arc4.UInt256:
        return arc4.UInt256.from_log(a)

    @arc4.abimethod()
    def verify_ufixednxm_bytes(
        self, a: arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]
    ) -> Bytes:
        return a.bytes

    @arc4.abimethod()
    def verify_bigufixednxm_bytes(
        self, a: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]
    ) -> Bytes:
        return a.bytes

    @arc4.abimethod()
    def verify_ufixednxm_from_bytes(
        self, a: Bytes
    ) -> arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]:
        return arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_bytes(a)

    @arc4.abimethod()
    def verify_bigufixednxm_from_bytes(
        self, a: Bytes
    ) -> arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]:
        return arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_bytes(a)

    @arc4.abimethod()
    def verify_ufixednxm_from_log(
        self, a: Bytes
    ) -> arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]:
        return arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_log(a)

    @arc4.abimethod()
    def verify_bigufixednxm_from_log(
        self, a: Bytes
    ) -> arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]:
        return arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_log(a)

    @arc4.abimethod
    def verify_string_init(self, a: String) -> arc4.String:
        result = arc4.String(String("Hello, ") + a)
        return result

    @arc4.abimethod
    def verify_string_add(self, a: arc4.String, b: arc4.String) -> arc4.String:
        result = a + b
        return result

    @arc4.abimethod()
    def verify_string_eq(self, a: arc4.String, b: arc4.String) -> bool:
        return a == b

    @arc4.abimethod()
    def verify_string_bytes(self, a: String) -> Bytes:
        result = arc4.String(a)
        return result.bytes

    @arc4.abimethod()
    def verify_string_from_bytes(self, a: Bytes) -> arc4.String:
        return arc4.String.from_bytes(a)

    @arc4.abimethod()
    def verify_string_from_log(self, a: Bytes) -> arc4.String:
        return arc4.String.from_log(a)

    @arc4.abimethod()
    def verify_bool_bytes(self, a: arc4.Bool) -> Bytes:
        return a.bytes

    @arc4.abimethod()
    def verify_bool_from_bytes(self, a: Bytes) -> arc4.Bool:
        return arc4.Bool.from_bytes(a)

    @arc4.abimethod()
    def verify_bool_from_log(self, a: Bytes) -> arc4.Bool:
        return arc4.Bool.from_log(a)
