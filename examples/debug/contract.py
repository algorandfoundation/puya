from algopy import UInt64, arc4, subroutine


class DebugContract(arc4.ARC4Contract):
    @arc4.abimethod
    def test(self, x: UInt64, y: UInt64, z: UInt64) -> UInt64:

        a = x
        if x < y:
            a = a + y
        elif x < z:
            a = a + z

        if y < z:
            a *= some_func(a, y)
        else:
            a *= some_func(a, z)

        if a < x:
            a += x
        if a < y:
            a += y
        if a < z:
            a += z

        return a


@subroutine
def some_func(a: UInt64, b: UInt64) -> UInt64:
    a += b
    b *= a
    a += b
    a *= 2
    return a
