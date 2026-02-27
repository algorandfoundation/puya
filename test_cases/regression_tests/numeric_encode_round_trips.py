from algopy import ARC4Contract, BigUInt, UInt64, arc4, public


class NumericEncodeRoundTrips(ARC4Contract):
    # ARC4 UInt -> UInt64 -> ARC4 UInt
    @public
    def arc4_uint32_via_uint64(self, x: arc4.UInt32) -> arc4.UInt32:
        return arc4.UInt32(x.as_uint64())

    @public
    def arc4_uint64_via_uint64(self, x: arc4.UInt64) -> arc4.UInt64:
        return arc4.UInt64(x.as_uint64())

    @public
    def arc4_uint128_via_uint64(self, x: arc4.UInt128) -> arc4.UInt128:
        return arc4.UInt128(x.as_uint64())

    # UInt64 -> ARC4 UInt -> UInt64
    @public
    def uint64_via_arc4_uint32(self, x: UInt64) -> UInt64:
        return arc4.UInt32(x).as_uint64()

    @public
    def uint64_via_arc4_uint64(self, x: UInt64) -> UInt64:
        return arc4.UInt64(x).as_uint64()

    @public
    def uint64_via_arc4_uint128(self, x: UInt64) -> UInt64:
        return arc4.UInt128(x).as_uint64()

    # ARC4 UInt -> BigUInt -> ARC4 UInt
    @public
    def arc4_uint32_via_biguint(self, x: arc4.UInt32) -> arc4.UInt32:
        return arc4.UInt32(x.as_biguint())

    @public
    def arc4_uint64_via_biguint(self, x: arc4.UInt64) -> arc4.UInt64:
        return arc4.UInt64(x.as_biguint())

    @public
    def arc4_uint128_via_biguint(self, x: arc4.UInt128) -> arc4.UInt128:
        return arc4.UInt128(x.as_biguint())

    # BigUInt -> ARC4 UInt -> BigUInt
    @public
    def biguint_via_arc4_uint32(self, x: BigUInt) -> BigUInt:
        return arc4.UInt32(x).as_biguint()

    @public
    def biguint_via_arc4_uint64(self, x: BigUInt) -> BigUInt:
        return arc4.UInt64(x).as_biguint()

    @public
    def biguint_via_arc4_uint128(self, x: BigUInt) -> BigUInt:
        return arc4.UInt128(x).as_biguint()
