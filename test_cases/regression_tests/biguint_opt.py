from algopy import BigUInt, UInt64, arc4, op


class ConstBigIntToIntOverflow(arc4.ARC4Contract):
    @arc4.abimethod()
    def get_abs_bound1(self, upper_bound: UInt64) -> UInt64:
        abs_bound = lower_bound = UInt64(0)
        if upper_bound:
            # if upper bound is truthy, then this will error at run time
            # but optimizer should not replace this op in this case since it is guarded
            # TODO: it would be nice if the optimizer could just replace this failure
            #       with an err, but that would require terminating the block as part of optimizing
            abs_bound = op.btoi((BigUInt(1 << 64) - lower_bound).bytes)

        return abs_bound

    @arc4.abimethod()
    def get_abs_bound2(self) -> UInt64:
        # this variant resulted in the optimization bug appearing in the router after inlining
        # this function
        abs_bound = op.btoi((BigUInt(1 << 64) - 0).bytes)

        return abs_bound
