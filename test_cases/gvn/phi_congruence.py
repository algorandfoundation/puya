from algopy import Contract, Txn, UInt64, log, op, subroutine, urange


class PhiCongruenceContract(Contract):
    """Test contract for GVN phi handling.

    Contains patterns exercising:
    - SCC-based phi congruence (cross-assigned variables in loops)
    - Redundant phi elimination (different registers, same VN at join points)
    """

    def approval_program(self) -> bool:
        assert test_cross_assignment(UInt64(42)) == 84
        assert test_cross_assignment(UInt64(0)) == 0
        assert test_triple_cycle(UInt64(10)) == 30
        assert test_redundant_phi(Txn.num_app_args, UInt64(5)) == Txn.num_app_args | 5
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_redundant_phi(a: UInt64, b: UInt64) -> UInt64:
    """Commutative expressions selected by a branch — redundant phi for GVN.

    val1 = a | b and val2 = b | a are syntactically different (so the frontend
    and copy propagation keep them as separate registers), but GVN canonicalises
    commutative operand VNs and assigns them the same VN.

    In SSA after copy propagation:
        val1 = a | b        (VN=X, commutative-canonical)
        val2 = b | a        (same canonical key, also VN=X)
        if ...:  ...
        else:    ...
        result = phi(val1, val2)   (different registers, but same VN → redundant)

    GVN eliminates the phi and the duplicate expression.
    """
    val1 = a | b
    val2 = b | a
    if a > b:
        log(op.itob(a))  # side effect to keep branch alive
        result = val1
    else:
        log(op.itob(b))
        result = val2
    return result


@subroutine(inline=False)
def test_cross_assignment(n: UInt64) -> UInt64:
    """Two variables initialized to the same value and cross-assigned in a loop.

    In SSA this becomes:
        x = phi(n, y_prev)
        y = phi(n, x_prev)
    Both phis have the same external VN (n) and reference each other,
    forming an SCC. Since external VNs match, x == y throughout.
    """
    x = n
    y = n
    for _i in urange(10):
        tmp = x
        x = y
        y = tmp
    # x == y == n, so x + y == 2*n
    return x + y


@subroutine(inline=False)
def test_triple_cycle(n: UInt64) -> UInt64:
    """Three variables in a cycle, all initialized to the same value.

    In SSA:
        a = phi(n, c_prev)
        b = phi(n, a_prev)
        c = phi(n, b_prev)
    SCC of size 3, all external VNs are n → all congruent.
    """
    a = n
    b = n
    c = n
    for _i in urange(5):
        tmp_a = a
        tmp_b = b
        a = c
        b = tmp_a
        c = tmp_b
    # a == b == c == n, so a + b + c == 3*n
    return a + b + c
