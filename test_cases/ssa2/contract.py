from puyapy import Contract, UInt64, subroutine, urange


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        a = UInt64(1) + 2
        b = UInt64(4) * 5

        # while a < UInt64(5):
        #     b = b + a
        #     a = a + 1

        for i in urange(5):
            b = b + a
            a = a + i
        return a + b

        # if a < b:
        #     if b < 2:
        #         b = 3 + UInt64(2)
        #         c = a + b
        #     else:
        #         b = 2 * a
        #         if ((3 * 4) + 2) * b:
        #             c = UInt64(2)
        #         else:
        #             return UInt64(3)
        # elif b == a:
        #     c = a * b
        # else:
        #     c = a - b
        # c = c + one_hundred(c)
        # return c

    def clear_state_program(self) -> UInt64:
        return one_hundred(UInt64(40))


@subroutine
def one_hundred(c: UInt64) -> UInt64:
    a = UInt64(25)
    b = UInt64(2)
    if a < c:
        b = UInt64(1)
        a = UInt64(100)

    b *= b
    return a * b
