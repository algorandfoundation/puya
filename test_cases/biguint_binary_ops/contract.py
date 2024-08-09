from algopy import BigUInt, Contract, op, subroutine


class BiguintBinaryOps(Contract):
    def approval_program(self) -> bool:
        left = BigUInt(58446744073709552000)
        right = BigUInt(18446744073709552000)
        # Math
        assert left + right == BigUInt(76893488147419104000)
        assert left - right == BigUInt(40000000000000000000)
        assert left * right == BigUInt(1078152129869320557630474056040704000000)
        assert left // right == BigUInt(3)
        assert left % right == BigUInt(3106511852580896000)
        # Boolean
        assert not (left < right)
        assert not (left <= right)
        assert left > right
        assert left >= right
        assert not (left == right)  # noqa: SIM201
        assert left != right
        # Bitwise
        assert left | right == BigUInt(58446744073709552000)
        assert left & right == BigUInt(18446744073709552000)
        assert left ^ right == BigUInt(40000000000000000000)
        assert bitwise_ops(left) == bitwise_ops(left)
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def bitwise_ops(value: BigUInt) -> BigUInt:
    low128 = BigUInt.from_bytes(op.bzero(16) + ~op.bzero(16))
    wide_value_compl = (value ^ low128) + BigUInt(1)

    return wide_value_compl & low128
