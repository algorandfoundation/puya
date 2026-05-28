from algopy import ARC4Contract, UInt64, public, subroutine, urange


class SccTwoExternalsContract(ARC4Contract):
    """Smallest test exercising the SCC pre-pass's pessimistic classification.

    Two phis form a multi-member SCC with two distinct external init
    Registers (the parameters ``a`` and ``b``). The SCC cannot collapse to
    a single VN — odd iterations swap ``x`` and ``y`` — so the pre-pass
    marks both phis pessimistic and ``visit_phi`` short-circuits the
    redundancy claim. Without the pre-pass, optimistic iteration would
    converge to the same partition in 2-3 walks (small SCC).
    """

    @public
    def test_alternating(self, a: UInt64, b: UInt64, n: UInt64) -> UInt64:
        return alternating(a, b, n)


@subroutine(inline=False)
def alternating(a: UInt64, b: UInt64, n: UInt64) -> UInt64:
    x = a
    y = b
    s = UInt64(0)
    for i in urange(n):
        x, y = y, x
        s += i
    return x + y + s
