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

    # bool-context one-const folds: an arithmetic-with-const expression used directly as
    # a branch condition. intrinsic_simplification (which runs before GVN at O1) folds
    # these via the bool-context simplifier. Each returns 1 iff the condition is truthy.

    @public
    def cond_mul_one_l(self, x: UInt64) -> UInt64:
        # 1 * x as a condition -> x
        if UInt64(1) * x:
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_mul_one_r(self, x: UInt64) -> UInt64:
        # x * 1 as a condition -> x
        if x * UInt64(1):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_mul_zero(self, x: UInt64) -> UInt64:
        # x * 0 as a condition -> 0 (always false)
        if x * UInt64(0):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_div_one(self, x: UInt64) -> UInt64:
        # x // 1 as a condition -> x
        if x // UInt64(1):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_mod_one(self, x: UInt64) -> UInt64:
        # x % 1 as a condition -> 0 (always false)
        if x % UInt64(1):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_add_zero_l(self, x: UInt64) -> UInt64:
        # 0 + x as a condition -> x
        if UInt64(0) + x:
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_add_zero_r(self, x: UInt64) -> UInt64:
        # x + 0 as a condition -> x
        if x + UInt64(0):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_sub_zero(self, x: UInt64) -> UInt64:
        # x - 0 as a condition -> x
        if x - UInt64(0):
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_gt_zero(self, b: UInt64) -> UInt64:
        # 0 > b as a condition -> 0 (always false)
        if UInt64(0) > b:
            return UInt64(1)
        return UInt64(0)

    @public
    def cond_and_false(self, a: bool) -> UInt64:
        # `a and False` materialises &&(a, 0); as a condition -> 0 (always false)
        cond = a and False
        if cond:
            return UInt64(1)
        return UInt64(0)

    # value-context one-const folds where the surviving operand is a bool and the
    # comparison result is used as a value (not a branch condition), so GVN folds it.

    @public
    def val_gte_one(self, a: bool) -> bool:
        # (a >= 1) -> a   (a is a bool)
        r = a >= UInt64(1)
        return r

    @public
    def val_lte_one(self, b: bool) -> bool:
        # (1 <= b) -> b   (b is a bool)
        r = UInt64(1) <= b
        return r

    @public
    def val_lt_zero(self, b: bool) -> bool:
        # (0 < b) -> b   (b is a bool)
        r = UInt64(0) < b
        return r

    @public
    def val_gt_zero(self, a: bool) -> bool:
        # (a > 0) -> a   (a is a bool)
        r = a > UInt64(0)
        return r
