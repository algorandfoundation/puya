from algopy import BigUInt, Contract, Txn, UInt64, op, subroutine


class AlgebraicIdentitiesContract(Contract):
    """GVN algebraic identities and comparison canonicalisation that render asserts
    redundant: self-operand folds (x-x, x&x, x|x), one-const algebra visible only
    through a phi (x b* 1 -> x), swapped-predicate equivalence (a<b == b>a) and
    negation-aware numbering (!(a>=b) == a<b).
    """

    def approval_program(self) -> bool:
        test_self_sub(BigUInt(42), UInt64(42))
        test_self_bitwise(UInt64(42))
        test_one_const(BigUInt(42), selector=True)
        test_one_const(BigUInt(42), selector=False)
        a = Txn.num_app_args
        b = a + 1  # a < b always holds
        test_uint64_swaps(a, b)
        test_biguint_swaps(BigUInt(1), BigUInt(2))
        test_uint64_negated(a, b)
        test_biguint_negated(BigUInt(a), BigUInt(b))
        test_uint64_double_negated(a, b)
        test_biguint_double_negated(BigUInt(a), BigUInt(b))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_self_sub(x: BigUInt, y: UInt64) -> None:
    assert x - x == 0
    assert y - y == 0


@subroutine(inline=False)
def test_self_bitwise(y: UInt64) -> None:
    assert (y & y) == y
    assert (y | y) == y


@subroutine(inline=False)
def test_one_const(x: BigUInt, *, selector: bool) -> None:
    # `one` is 1 via two different exprs across a phi, so only GVN sees it constant
    if selector:
        one = BigUInt.from_bytes((op.bzero(65) + b"\x01")[-10:])
    else:
        one = BigUInt.from_bytes((op.bzero(66) + b"\x01")[-10:])
    assert x * one == x
    assert one * x == x


@subroutine(inline=False)
def test_uint64_swaps(a: UInt64, b: UInt64) -> None:
    assert a < b
    assert b > a
    assert a <= b
    assert b >= a


@subroutine(inline=False)
def test_biguint_swaps(a: BigUInt, b: BigUInt) -> None:
    assert a < b
    assert b > a
    assert a <= b
    assert b >= a


@subroutine(inline=False)
def test_uint64_negated(a: UInt64, b: UInt64) -> None:
    assert a < b
    assert not (a >= b)
    assert a <= b
    assert not (a > b)
    assert a != b
    eq_result = a == b
    assert not eq_result


@subroutine(inline=False)
def test_biguint_negated(a: BigUInt, b: BigUInt) -> None:
    assert a < b
    assert not (a >= b)
    assert a <= b
    assert not (a > b)
    assert a != b
    eq_result = a == b
    assert not eq_result


@subroutine(inline=False)
def test_uint64_double_negated(a: UInt64, b: UInt64) -> None:
    assert a < b
    neg = not (a < b)
    assert not neg


@subroutine(inline=False)
def test_biguint_double_negated(a: BigUInt, b: BigUInt) -> None:
    assert a < b
    neg = not (a < b)
    assert not neg
