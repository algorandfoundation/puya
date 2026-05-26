from algopy import ARC4Contract, UInt64, public, subroutine, urange


class IterationCapContract(ARC4Contract):
    """Test contract whose subroutine forces GVN's optimistic iteration to cap out.

    Deeply nested loops with a shared accumulator produce a phi chain
    whose corrections propagate at roughly one level per optimistic
    iteration. 14 levels exceeds _MAX_OPTIMISTIC_ITERATIONS = 16,
    triggering the pessimistic single-pass fallback.
    """

    @public
    def test_deep_nesting(self, n: UInt64) -> UInt64:
        return deep_nested_accumulator(n)


@subroutine(inline=False)
def deep_nested_accumulator(n: UInt64) -> UInt64:
    x = UInt64(0)
    for a1 in urange(n):
        for a2 in urange(n):
            for a3 in urange(n):
                for a4 in urange(n):
                    for a5 in urange(n):
                        for a6 in urange(n):
                            for a7 in urange(n):
                                for a8 in urange(n):
                                    for a9 in urange(n):
                                        for a10 in urange(n):
                                            for a11 in urange(n):
                                                for a12 in urange(n):
                                                    for a13 in urange(n):
                                                        for a14 in urange(n):
                                                            x += (
                                                                a1
                                                                + a2
                                                                + a3
                                                                + a4
                                                                + a5
                                                                + a6
                                                                + a7
                                                                + a8
                                                                + a9
                                                                + a10
                                                                + a11
                                                                + a12
                                                                + a13
                                                                + a14
                                                            )
    return x
