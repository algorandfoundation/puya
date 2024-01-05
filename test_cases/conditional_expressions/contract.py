from puyapy import Contract, UInt64, itob, log, subroutine


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        a = UInt64(1)
        b = UInt64(2)

        c = a or b
        d = b and a

        e = self.expensive_op(UInt64(0)) or self.side_effecting_op(UInt64(1))
        f = self.expensive_op(UInt64(3)) or self.side_effecting_op(UInt64(42))

        g = self.side_effecting_op(UInt64(0)) and self.expensive_op(UInt64(42))
        h = self.side_effecting_op(UInt64(2)) and self.expensive_op(UInt64(3))

        i = a if b < c else d + e

        result = a * b * c * d * f * h - e - g + i

        log(itob(result))

        return result

    def clear_state_program(self) -> UInt64:
        return UInt64(0)

    @subroutine
    def expensive_op(self, val: UInt64) -> UInt64:
        assert val != 42, "Can't be 42"
        log(b"expensive_op")
        return val

    @subroutine
    def side_effecting_op(self, val: UInt64) -> UInt64:
        assert val != 42, "Can't be 42"
        log(b"side_effecting_op")
        return val
