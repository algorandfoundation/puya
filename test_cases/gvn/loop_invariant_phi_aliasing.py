from algopy import ARC4Contract, UInt64, public, subroutine, urange


class LoopInvariantPhiAliasingContract(ARC4Contract):
    @public
    def run(self, x: UInt64, y: UInt64) -> UInt64:
        return loop_invariant_phi_aliasing(x, y)


@subroutine(inline=False)
def loop_invariant_phi_aliasing(x: UInt64, y: UInt64) -> UInt64:
    """Loop with a loop-invariant expression that shares the iter-1 optimistic
    VN of a loop-carried expression.

    In SSA:
        phi_z = phi(x, z_update)            # loop-carried, header
        a     = phi_z + y                   # depends on phi_z
        b     = x + y                       # loop-invariant
        z_update = a + b                    # back-edge

    On the first optimistic-iteration walk, the back-edge arg of phi_z is
    filtered out, so phi_z gets VN(x). With phi_z ≡ x, both `a` and `b`
    have the structural key `(add, VN(x), VN(y))` and share a VN. On the
    second walk, phi_z is non-redundant and `a`'s key shifts — but the
    finding posits that `_identity_vns` memoisation in `fresh_vns` leaks
    the iter-1 VN, causing `a` and `b` to remain in the same equivalence
    set despite being structurally different. If GVN replaces `b` with
    `a`, the runtime value diverges because `a` varies per iteration
    whereas `b` is loop-invariant.

    Closed forms:
        Correct: z evolves by (2y + x) per iteration → z = x + 10*(2y + x)
        Buggy (b replaced with a): z_new = 2*a = 2*(z + y), so
            z = (z + y) * 2 each iteration after the first
    """
    z = x
    for _i in urange(10):
        a = z + y
        b = x + y
        z = a + b
    return z
