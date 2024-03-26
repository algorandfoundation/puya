from algopy import Bytes, UInt64, op, subroutine, urange

ONE = 1
HELLO = "👋".encode()


@subroutine
def three() -> UInt64:
    a = UInt64(1) + ONE
    b = a + 1
    return b


@subroutine
def hello_world() -> Bytes:
    hello = Bytes(HELLO)
    comma = Bytes.from_base64("4aCI")
    world = Bytes(b" world")
    return hello + comma + world


@subroutine
def safe_add(x: UInt64, y: UInt64) -> tuple[UInt64, bool]:
    """Add two UInt64 and return the result as well as whether it overflowed or not"""
    hi, lo = op.addw(x, y)
    did_overflow = hi > 0
    return lo, did_overflow


@subroutine
def safe_six() -> tuple[UInt64, bool]:
    """lollll"""
    return safe_add(three(), three())


@subroutine
def itoa(i: UInt64) -> Bytes:
    """Itoa converts an integer to the ascii byte string it represents"""
    digits = Bytes(b"0123456789")
    radix = digits.length
    if i < radix:
        return digits[i]
    return itoa(i // radix) + digits[i % radix]


@subroutine
def itoa_loop(num: UInt64) -> Bytes:
    """Itoa converts an integer to the ascii byte string it represents"""
    digits = Bytes(b"0123456789")
    result = Bytes(b"")
    while num >= 10:
        result = digits[num % 10] + result
        num //= 10
    result = digits[num] + result
    return result


@subroutine
def inefficient_multiply(a: UInt64, b: UInt64) -> UInt64:
    if a == 0 or b == 0:
        return a
    if a < b:
        smaller = a
        bigger = b
    else:
        smaller = b
        bigger = a
    result = UInt64(0)
    for _i in urange(smaller):
        result += bigger
    return result


@subroutine
def test_and_uint64() -> UInt64:
    return UInt64(1) and UInt64(2)
