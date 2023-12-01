from algopy import Contract, UInt64


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        a = UInt64(75)
        c = UInt64(77)
        b = a + c
        a = b + 5
        c = b + a

        return c

    def clear_state_program(self) -> UInt64:
        return UInt64(1)
