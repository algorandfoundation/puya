from algopy import ARC4Contract, BigUInt, UInt64, arc4, public


class OneConstSimplificationContract(ARC4Contract):
    """GVN one-const algebraic simplifications that collapse to a value or operand.

    Each method passes a runtime value in and returns the simplified result, so
    the pytest test can assert the rewrite preserved semantics. The interesting
    operand is a constant (0/1) that GVN sees, triggering a one-const rule in
    `simplify_uint64_binary_op_one_const` / `simplify_bytes_binary_op_one_const`.
    """

    @public
    def mul_zero(self, x: UInt64) -> UInt64:
        # x * 0 -> 0
        return x * UInt64(0)

    @public
    def gt_zero(self, b: UInt64) -> bool:
        # 0 > b -> 0 (uint64 is never negative)
        return UInt64(0) > b

    @public
    def lte_one(self, x: UInt64) -> UInt64:
        # 1 <= x in a branch (bool context) -> x; so this returns 1 iff x != 0
        if UInt64(1) <= x:
            return UInt64(1)
        return UInt64(0)

    @public
    def or_false(self, a: bool) -> UInt64:
        # `a or False` with a constant RHS materialises a `||(a, 0)` op; used as a
        # branch condition (bool context) it simplifies to `a`.
        cond = a or False
        if cond:
            return UInt64(1)
        return UInt64(0)

    @public
    def bmul_zero(self, x: arc4.UInt256) -> arc4.UInt256:
        # x b* 0 -> 0
        return arc4.UInt256(x.as_biguint() * BigUInt(0))

    @public
    def badd_zero_left(self, x: arc4.UInt256) -> arc4.UInt256:
        # 0 b+ x -> x
        return arc4.UInt256(BigUInt(0) + x.as_biguint())

    @public
    def badd_zero_right(self, x: arc4.UInt256) -> arc4.UInt256:
        # x b+ 0 -> x
        return arc4.UInt256(x.as_biguint() + BigUInt(0))

    @public
    def bsub_zero(self, x: arc4.UInt256) -> arc4.UInt256:
        # x b- 0 -> x
        return arc4.UInt256(x.as_biguint() - BigUInt(0))

    @public
    def bdiv_one(self, x: arc4.UInt256) -> arc4.UInt256:
        # x b/ 1 -> x
        return arc4.UInt256(x.as_biguint() // BigUInt(1))

    @public
    def cond_gt_zero(self, b: UInt64) -> UInt64:
        # bool context: `0 > b` used directly as a branch condition folds to 0 (a uint64
        # is never negative). Returns 0 for every b.
        if UInt64(0) > b:
            return UInt64(1)
        return UInt64(0)

    # value context: a comparison whose surviving operand is a bool and whose result is
    # used as a value (not a branch condition) — GVN folds these to the bool operand.

    @public
    def val_lte_one(self, b: bool) -> bool:
        # (1 <= b) -> b
        r = UInt64(1) <= b
        return r

    @public
    def val_lt_zero(self, b: bool) -> bool:
        # (0 < b) -> b
        r = UInt64(0) < b
        return r
