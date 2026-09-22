from algopy import ARC4Contract, BigUInt, Bytes, UInt64, arc4, op, public


class OneConstSimplificationContract(ARC4Contract):
    """GVN one-const algebra: an op with one constant operand (0 or 1) collapses to a
    value or to the other operand, in both branch-condition and value contexts. The
    `UInt64(...)` wrappers are load-bearing — without them the puyapy frontend flips the
    literal around (correct, but bypasses the lines under test).
    """

    @public
    def mul_zero(self, x: UInt64) -> UInt64:
        return x * 0

    @public
    def gt_zero(self, b: UInt64) -> bool:
        return UInt64(0) > b

    @public
    def lte_one(self, x: UInt64) -> UInt64:
        if UInt64(1) <= x:
            return UInt64(1)
        return UInt64(0)

    @public
    def or_false(self, a: bool) -> UInt64:
        cond = a or False
        if cond:
            return UInt64(1)
        return UInt64(0)

    @public
    def bmul_zero(self, x: arc4.UInt256) -> arc4.UInt256:
        return arc4.UInt256(x.as_biguint() * 0)

    @public
    def badd_zero_left(self, x: arc4.UInt256) -> arc4.UInt256:
        return arc4.UInt256(0 + x.as_biguint())

    @public
    def badd_zero_right(self, x: arc4.UInt256) -> arc4.UInt256:
        return arc4.UInt256(x.as_biguint() + 0)

    @public
    def bsub_zero(self, x: arc4.UInt256) -> arc4.UInt256:
        return arc4.UInt256(x.as_biguint() - 0)

    @public
    def bdiv_one(self, x: arc4.UInt256) -> arc4.UInt256:
        return arc4.UInt256(x.as_biguint() // 1)

    @public
    def cond_gt_zero(self, b: UInt64) -> UInt64:
        if UInt64(0) > b:
            return UInt64(1)
        return UInt64(0)

    @public
    def val_lte_one(self, b: bool) -> bool:
        r = UInt64(1) <= b
        return r

    @public
    def val_lt_zero(self, b: bool) -> bool:
        r = UInt64(0) < b
        return r


class DeclinedConstFoldContract(ARC4Contract):
    """Ops where GVN sees constant operands but declines to fold because the op would
    trap at runtime — exercising the decline (`return None`) branches of the fold helpers.
    Zero divisors are built via btoi/bzero so the frontend doesn't reject them while GVN
    still proves them constant.
    """

    @public
    def expw_zero_zero(self) -> UInt64:
        hi, lo = op.expw(UInt64(0), UInt64(0))
        return hi + lo

    @public
    def expw_overflow(self) -> UInt64:
        hi, lo = op.expw(UInt64(2), UInt64(128))
        return hi + lo

    @public
    def divw_div_zero(self) -> UInt64:
        return op.divw(UInt64(0), UInt64(5), UInt64(0))

    @public
    def divw_overflow(self) -> UInt64:
        return op.divw(UInt64(1), UInt64(0), UInt64(1))

    @public
    def divmodw_div_zero(self) -> UInt64:
        qh, ql, rh, rl = op.divmodw(UInt64(0), UInt64(5), UInt64(0), UInt64(0))
        return qh + ql + rh + rl

    @public
    def setbyte_value_oob(self) -> Bytes:
        return op.setbyte(Bytes(b"AB"), UInt64(0), UInt64(256))

    @public
    def bsqrt_too_long(self) -> arc4.UInt512:
        arg = BigUInt.from_bytes(Bytes(b"\x01" + b"\x00" * 64))
        return arc4.UInt512(op.bsqrt(arg))

    @public
    def div_by_zero(self) -> UInt64:
        return UInt64(5) // op.btoi(Bytes(b"\x00"))

    @public
    def mod_by_zero(self) -> UInt64:
        return UInt64(5) % op.btoi(Bytes(b"\x00"))

    @public
    def biguint_mod_by_zero(self) -> arc4.UInt256:
        return arc4.UInt256(BigUInt(5) % BigUInt.from_bytes(op.bzero(UInt64(1))))
