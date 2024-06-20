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

    @arc4.abimethod()
    def verify_emit(  # noqa: PLR0913
        self,
        a: arc4.String,
        b: arc4.UInt512,
        c: arc4.UInt64,
        d: arc4.DynamicBytes,
        e: arc4.UInt64,
        f: arc4.Bool,
        g: arc4.DynamicBytes,
        h: arc4.String,
        m: arc4.UIntN[typing.Literal[64]],
        n: arc4.BigUIntN[typing.Literal[256]],
        o: arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]],
        p: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]],
        q: arc4.Bool,
        r: Bytes,
        s: Bytes,
        t: Bytes,
    ) -> None:
        arc4_r = arc4.StaticArray[arc4.UInt8, typing.Literal[3]].from_bytes(r)
        arc4_s = arc4.DynamicArray[arc4.UInt16].from_bytes(s)
        arc4_t = arc4.Tuple[arc4.UInt32, arc4.UInt64, arc4.String].from_bytes(t)

        arc4.emit(SwappedArc4(m, n, o, p, q, arc4_r, arc4_s, arc4_t))
        arc4.emit(
            "Swapped",
            a,
            b,
            c,
            d.copy(),
            e,
            f,
            g.copy(),
            h,
            m,
            n,
            o,
            p,
            q,
            arc4_r.copy(),
            arc4_s.copy(),
            arc4_t,
        )
        arc4.emit(
            "Swapped(string,uint512,uint64,byte[],uint64,bool,byte[],string,uint64,uint256,ufixed32x8,ufixed256x16,bool,uint8[3],uint16[],(uint32,uint64,string))",
            a,
            b,
            c,
            d.copy(),
            e,
            f,
            g.copy(),
            h,
            m,
            n,
            o,
            p,
            q,
            arc4_r.copy(),
            arc4_s.copy(),
            arc4_t,
        )


class SwappedArc4(arc4.Struct):
    m: arc4.UIntN[typing.Literal[64]]
    n: arc4.BigUIntN[typing.Literal[256]]
    o: arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]
    p: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]
    q: arc4.Bool
    r: arc4.StaticArray[arc4.UInt8, typing.Literal[3]]
    s: arc4.DynamicArray[arc4.UInt16]
    t: arc4.Tuple[arc4.UInt32, arc4.UInt64, arc4.String]
