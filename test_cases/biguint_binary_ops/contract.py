from algopy import BigUInt, Contract


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
        return True

    def clear_state_program(self) -> bool:
        return True
