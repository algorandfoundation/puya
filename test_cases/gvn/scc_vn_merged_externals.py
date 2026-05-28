from algopy import ARC4Contract, UInt64, public, subroutine, urange


class SccVnMergedExternalsContract(ARC4Contract):
    """Smallest test exercising VN-aware SCC classification.

    Two phis form a multi-member SCC. The external init Registers come
    from commutative-equivalent expressions ``a | b`` and ``b | a``,
    which GVN canonicalises to the same VN even though they're distinct
    Registers. Under Register-identity classification this SCC was
    pessimistic; under VN-aware classification it collapses, because
    every external argument resolves to the same VN. ``x`` and ``y``
    then carry the same VN throughout the loop and the closing
    ``x + y`` becomes ``2 * (a | b)``.
    """

    @public
    def test_commutative_externals(self, a: UInt64, b: UInt64, n: UInt64) -> UInt64:
        return alternating_with_commutative_inits(a, b, n)


@subroutine(inline=False)
def alternating_with_commutative_inits(a: UInt64, b: UInt64, n: UInt64) -> UInt64:
    e1 = a | b
    e2 = b | a
    x = e1
    y = e2
    s = UInt64(0)
    for i in urange(n):
        x, y = y, x
        s += i
    return x + y + s
