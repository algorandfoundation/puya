from puyapy import BigUInt, Contract, subroutine


class BiguintBinaryOps(Contract):
    def approval_program(self) -> bool:
        (
            add,
            subtract,
            multiply,
            divide,
            mod,
            lt,
            lte,
            gt,
            gte,
            eq,
            neq,
            b_or,
            b_and,
            b_xor,
        ) = do_some_ops(BigUInt(58446744073709552000), BigUInt(18446744073709552000))

        assert add == BigUInt(76893488147419104000)
        assert subtract == BigUInt(40000000000000000000)
        assert multiply == BigUInt(1078152129869320557630474056040704000000)
        assert divide == BigUInt(3)
        assert mod == BigUInt(3106511852580896000)
        assert not lt
        assert not lte
        assert gt
        assert gte
        assert not eq
        assert neq
        assert b_or == BigUInt(58446744073709552000)
        assert b_and == BigUInt(18446744073709552000)
        assert b_xor == BigUInt(40000000000000000000)
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def do_some_ops(
    left: BigUInt, right: BigUInt
) -> tuple[
    BigUInt,
    BigUInt,
    BigUInt,
    BigUInt,
    BigUInt,
    bool,
    bool,
    bool,
    bool,
    bool,
    bool,
    BigUInt,
    BigUInt,
    BigUInt,
]:
    return (
        # Math
        left + right,
        left - right,
        left * right,
        left // right,
        left % right,
        # Boolean
        left < right,
        left <= right,
        left > right,
        left >= right,
        left == right,
        left != right,
        # Bitwise
        left | right,
        left & right,
        left ^ right,
    )
