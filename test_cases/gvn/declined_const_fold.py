from algopy import ARC4Contract, BigUInt, Bytes, UInt64, arc4, op, public


class DeclinedConstFoldContract(ARC4Contract):
    """Ops where GVN sees constant operands but declines to fold because the op
    would fail at runtime — exercising the `return None` branches of the fold
    helpers. The op is left in place, so every method traps when called.

    All operands are visible to GVN as constants:
    - wide-math ops (expw/divw/divmodw) are folded only by GVN, so direct literals
      reach it untouched;
    - for div/mod the zero divisor is produced via `btoi`/`bzero` of a constant so
      the frontend doesn't reject it, but GVN still proves it constant.
    """

    @public
    def expw_zero_zero(self) -> UInt64:
        # 0 ** 0 is undefined on the AVM
        hi, lo = op.expw(UInt64(0), UInt64(0))
        return hi + lo

    @public
    def expw_overflow(self) -> UInt64:
        # 2 ** 128 overflows uint128
        hi, lo = op.expw(UInt64(2), UInt64(128))
        return hi + lo

    @public
    def divw_div_zero(self) -> UInt64:
        # divisor 0
        return op.divw(UInt64(0), UInt64(5), UInt64(0))

    @public
    def divw_overflow(self) -> UInt64:
        # (2**64) // 1 overflows uint64
        return op.divw(UInt64(1), UInt64(0), UInt64(1))

    @public
    def divmodw_div_zero(self) -> UInt64:
        # divisor 0
        qh, ql, rh, rl = op.divmodw(UInt64(0), UInt64(5), UInt64(0), UInt64(0))
        return qh + ql + rh + rl

    @public
    def setbyte_value_oob(self) -> Bytes:
        # byte value 256 exceeds a single byte
        return op.setbyte(Bytes(b"AB"), UInt64(0), UInt64(256))

    @public
    def bsqrt_too_long(self) -> arc4.UInt512:
        # 65-byte (520-bit) operand exceeds bsqrt's 64-byte input limit
        arg = BigUInt.from_bytes(Bytes(b"\x01" + b"\x00" * 64))
        return arc4.UInt512(op.bsqrt(arg))

    @public
    def div_by_zero(self) -> UInt64:
        # 5 // 0
        return UInt64(5) // op.btoi(Bytes(b"\x00"))

    @public
    def mod_by_zero(self) -> UInt64:
        # 5 % 0
        return UInt64(5) % op.btoi(Bytes(b"\x00"))

    @public
    def biguint_mod_by_zero(self) -> arc4.UInt256:
        # 5 b% 0
        return arc4.UInt256(BigUInt(5) % BigUInt.from_bytes(op.bzero(UInt64(1))))
