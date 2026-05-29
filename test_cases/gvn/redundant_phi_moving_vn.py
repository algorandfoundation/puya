from algopy import ARC4Contract, UInt64, public, subroutine


class RedundantPhiMovingVnContract(ARC4Contract):
    @public
    def run(self, n: UInt64, y: UInt64, *, cond: bool) -> UInt64:
        return redundant_phi_moving_vn(n, y, cond=cond)


@subroutine(inline=False)
def redundant_phi_moving_vn(n: UInt64, y: UInt64, *, cond: bool) -> UInt64:
    """Fire GVN's monotonic-convergence guard via a redundant phi with a moving VN.

    In SSA, the loop produces:

        z_hdr = phi(0 <- pre, z_upd <- latch)   # loop-carried accumulator
        # both arms of the branch compute the SAME expression:
        w_a   = z_hdr + y                        # in the `cond` arm
        w_b   = z_hdr + y                        # in the `not cond` arm
        w_mrg = phi(w_a <- arm_a, w_b <- arm_b)  # NON-trivial (distinct regs)
        z_upd = w_mrg + 1                         # back-edge

    `w_mrg` is a non-trivial phi (its two args are distinct registers), so
    SSA-construction trivial-phi removal leaves it in place, and with no
    copy-propagation pass it survives into GVN's numbering walk. Both args
    structurally CSE to `add(VN(z_hdr), VN(y))`, so `w_mrg` is redundant —
    its single real VN.

    Across optimistic iterations that single VN MOVES:
      - iter 1: the back-edge arg of `z_hdr` is filtered (optimistic top), so
        `z_hdr` takes VN(0); both arms key to `add(VN(0), VN(y))`; `w_mrg`
        inherits that VN.
      - iter 2: `z_upd` is now numbered and differs from VN(0), so `z_hdr`
        downgrades to its stable VN; both arms now key to
        `add(stable, VN(y))` — a different VN. `w_mrg` is still redundant but
        its VN has flipped, so the monotonic-convergence guard pins it to its
        own stable VN.
    """
    z = UInt64(0)
    i = UInt64(0)
    while i < n:
        if cond:
            w = z + y
        else:
            w = z + y
        z = w + UInt64(1)
        i += UInt64(1)
    return z
