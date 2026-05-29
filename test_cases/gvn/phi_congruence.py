from algopy import ARC4Contract, UInt64, log, public, subroutine, urange


class PhiCongruenceContract(ARC4Contract):
    """GVN phi/SCC congruence and optimistic-iteration edge cases: redundant/congruent
    phis, SCC collapse vs pessimistic classification, the moving-VN and loop-invariant
    convergence guards, the iteration cap, and commutative-equality assert elimination.
    Methods wrap subroutines so the IR is easy to inspect.
    """

    @public
    def test_redundant_phi(self, a: UInt64, b: UInt64) -> UInt64:
        return test_redundant_phi(a, b)

    @public
    def test_cross_assignment(self, n: UInt64) -> UInt64:
        return test_cross_assignment(n)

    @public
    def test_triple_cycle(self, n: UInt64) -> UInt64:
        return test_triple_cycle(n)

    @public
    def test_replacement_chain(self, n: UInt64) -> UInt64:
        return test_replacement_chain(n)

    @public
    def test_alternating(self, a: UInt64, b: UInt64, n: UInt64) -> UInt64:
        return alternating(a, b, n)

    @public
    def test_commutative_externals(self, a: UInt64, b: UInt64, n: UInt64) -> UInt64:
        return alternating_with_commutative_inits(a, b, n)

    @public
    def test_moving_vn(self, n: UInt64, y: UInt64, *, cond: bool) -> UInt64:
        return redundant_phi_moving_vn(n, y, cond=cond)

    @public
    def test_loop_invariant(self, x: UInt64, y: UInt64) -> UInt64:
        return loop_invariant_phi_aliasing(x, y)

    @public
    def test_deep_nesting(self, n: UInt64) -> UInt64:
        return deep_nested_accumulator(n)

    @public
    def test_commutative_add_assert(self, a: UInt64, b: UInt64, *, cond: bool) -> UInt64:
        return commutative_add_assert(a, b, cond=cond)

    @public
    def test_nested_scc_collapse(self, n: UInt64, p: UInt64, q: UInt64) -> UInt64:
        return nested_scc_collapse(n, p, q)


@subroutine(inline=False)
def test_redundant_phi(a: UInt64, b: UInt64) -> UInt64:
    val1 = a | b
    val2 = b | a
    if a > b:
        log(a)
        result = val1
    else:
        log(b)
        result = val2
    return result


@subroutine(inline=False)
def test_cross_assignment(n: UInt64) -> UInt64:
    x = n
    y = n
    for _i in urange(10):
        tmp = x
        x = y
        y = tmp
    return x + y


@subroutine(inline=False)
def test_triple_cycle(n: UInt64) -> UInt64:
    a = n
    b = n
    c = n
    for _i in urange(5):
        tmp_a = a
        tmp_b = b
        a = c
        b = tmp_a
        c = tmp_b
    return a + b + c


@subroutine(inline=False)
def test_replacement_chain(n: UInt64) -> UInt64:
    """Odd `n` never exits the loop — runs until the op budget is exhausted."""
    a = n
    b = n
    while True:
        if not n:
            a = n
            b = n
        log(a)
        log(b)
        b = a
        a = b
        if n % 2 == 0:
            break
    return a + b


@subroutine(inline=False)
def alternating(a: UInt64, b: UInt64, n: UInt64) -> UInt64:
    x = a
    y = b
    s = UInt64(0)
    for i in urange(n):
        x, y = y, x
        s += i
    return x + y + s


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


@subroutine(inline=False)
def redundant_phi_moving_vn(n: UInt64, y: UInt64, *, cond: bool) -> UInt64:
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


@subroutine(inline=False)
def loop_invariant_phi_aliasing(x: UInt64, y: UInt64) -> UInt64:
    z = x
    for _i in urange(10):
        a = z + y
        b = x + y
        z = a + b
    return z


@subroutine(inline=False)
def deep_nested_accumulator(n: UInt64) -> UInt64:
    """14 nested loops build a deep phi chain — verifies large chains don't cause a
    linear increase in numbering iterations (which would exceed the hard cap and error)."""
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


@subroutine(inline=False)
def commutative_add_assert(a: UInt64, b: UInt64, *, cond: bool) -> UInt64:
    """The redundant `a + b` is NOT hoisted out of the branches (no PRE) — this is
    commutative-equality assert elimination, not CSE."""
    if cond:
        result = a + b
        log("cond: ", result)
    else:
        result = a + b
        log("!cond: ", result)
    assert result == (b + a)
    return result


@subroutine(inline=False)
def nested_scc_collapse(n: UInt64, p: UInt64, q: UInt64) -> UInt64:
    """Returns n for any p, q."""
    # The inner body resets v to n, so v flows through both loop headers unchanged and
    # their phis form a multi-member SCC whose only external value number is n.
    v = n
    i = UInt64(0)
    while i < p:
        j = UInt64(0)
        while j < q:
            v = n
            j += 1
        i += 1
    return v
