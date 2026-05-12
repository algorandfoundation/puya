"""Pure constant-folding helpers for AVM intrinsics that are folded
only by GVN (multi-return ops; see `intrinsic_simplification.COMPILE_TIME_CONSTANT_OPS`
for the categorisation).

Each `fold_*` takes raw `int` inputs, returns the raw result tuple, or
returns `None` if the inputs would cause the op to fail at runtime
(out-of-range, overflow, divide-by-zero, etc.). No model imports.
"""

from puya.ir.optimize.intrinsic_simplification import valid_uint64

_U64_MASK = (1 << 64) - 1


def fold_addw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    total = a + b
    return total >> 64, total & _U64_MASK


def fold_mulw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    product = a * b
    return product >> 64, product & _U64_MASK


def fold_expw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    if a == 0 and b == 0:
        return None  # 0**0 traps on AVM
    result = a**b
    if result.bit_length() > 128:
        return None  # would overflow uint128
    return result >> 64, result & _U64_MASK


def fold_divw(hi: int, lo: int, divisor: int) -> int | None:
    if not (valid_uint64(hi) and valid_uint64(lo) and valid_uint64(divisor)):
        return None
    if divisor == 0:
        return None
    dividend = (hi << 64) | lo
    quotient = dividend // divisor
    if not valid_uint64(quotient):
        return None
    return quotient


def fold_divmodw(h1: int, l1: int, h2: int, l2: int) -> tuple[int, int, int, int] | None:
    if not all(valid_uint64(x) for x in (h1, l1, h2, l2)):
        return None
    divisor = (h2 << 64) | l2
    if divisor == 0:
        return None
    dividend = (h1 << 64) | l1
    q, r = divmod(dividend, divisor)
    return q >> 64, q & _U64_MASK, r >> 64, r & _U64_MASK
