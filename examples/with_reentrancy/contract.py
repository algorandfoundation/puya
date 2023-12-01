from algopy import Bytes, Contract, UInt64, itob, log, subroutine


class WithReentrancy(Contract):
    """My re-entrant contract"""

    def approval_program(self) -> bool:
        log(itob(fibonacci(UInt64(5))))
        silly(UInt64(2))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def itoa(i: UInt64) -> Bytes:
    digits = Bytes(b"0123456789")
    radix = digits.length
    if i < radix:
        return digits[i]
    return itoa(i // radix) + digits[i % radix]


@subroutine
def fibonacci(n: UInt64) -> UInt64:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


@subroutine
def silly(x: UInt64) -> UInt64:
    x = x + 1
    result = silly2(x)
    log(Bytes(b"silly = ") + itoa(x))
    return result


@subroutine
def silly2(x: UInt64) -> UInt64:
    x = x + 2
    result = silly3(x)
    log(Bytes(b"silly2 = ") + itoa(x))
    return result


@subroutine
def silly3(x: UInt64) -> UInt64:
    is_even = x % 2 == 0
    a = x + 2
    if is_even:
        result = a * 2
        a = result // 2 - 2
    else:
        result = silly(x)

    if is_even:
        result = a
    log(Bytes(b"silly3 = ") + itoa(x))
    return result
