from algopy import Bytes, TemplateVar, UInt64, arc4, log, subroutine


class DebugContract(arc4.ARC4Contract):
    @arc4.abimethod
    def test(self, x: UInt64, y: UInt64, z: UInt64) -> UInt64:

        a = x * TemplateVar[UInt64]("A_MULT")
        b = x + y
        c = b * z
        if b < c:
            a = a + y
        elif a < c:
            a = a + z
        elif b < a:
            a = a * 3
        elif b > a:
            b = b + a

        if a + b < c:
            a *= some_func(a, y)
        else:
            b *= some_func(b, z)

        bee = itoa(b)
        c = a + b
        cea = itoa(c)

        if a < c:
            a += c
        if a < b:
            a += b
        if a < b + c:
            a = a * z

        aye = itoa(a)
        log(aye, bee, cea, sep=" ")

        return a


@subroutine
def some_func(a: UInt64, b: UInt64) -> UInt64:
    a += b
    b *= a
    a += b
    a *= 2
    x = a + b
    y = a * b
    return x if x < y else y


@subroutine
def itoa(i: UInt64) -> Bytes:
    digits = Bytes(b"0123456789")
    radix = digits.length
    if i < radix:
        return digits[i]
    return itoa(i // radix) + digits[i % radix]
