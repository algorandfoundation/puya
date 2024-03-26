from algopy import Contract, UInt64, log, op, subroutine, urange


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        a = UInt64(1) + 2
        b = UInt64(4) * 5

        a = a * b
        b = a + b

        while a < UInt64(5):
            b = b + a
            a = a + 1

        for i in urange(5):
            b = b + a
            a = a + i

        if a < b:
            if b < 2:
                b = 3 + UInt64(2)
                c = a + b
            else:
                b = 2 * a
                if ((3 * 4) + 2) * b:
                    c = UInt64(2)
                else:
                    return UInt64(3)
        elif b == a:
            c = a * b
        else:
            c = a - b
        c = c + one_hundred(c)
        c_bytes = op.itob(c)
        log(c_bytes)
        assert phi_in_equiv_class(UInt64(3), True) == 4
        assert phi_in_equiv_class(UInt64(3), False) == 4
        return c

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


@subroutine
def phi_in_equiv_class(y: UInt64, b: bool) -> UInt64:
    if b:
        tmp1 = y
        x = tmp1
    else:
        tmp2 = y
        x = tmp2
    x += 1
    return x
