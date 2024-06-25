import operator
import re
from collections.abc import Callable

import algokit_utils
import pytest
from algopy import UInt64
from algopy_testing.constants import MAX_UINT64, MAX_UINT512

from tests.common import AVMInvoker

_negative_value_error = "expected positive value"
_too_big64_error = re.escape(f"expected value <= {MAX_UINT64}")
_too_big512_error = re.escape(f"expected value <= {MAX_UINT512}")
_shift_error = "expected shift <= 63"

_undefined_error = re.escape("UInt64(0)**UInt64(0) is undefined")
_underflow_error = "- underflows"

_avm_underflow_error = "- would result negative"
_avm_zero_division_error = "/ 0"
_avm_zero_mod_error = "% 0"
_avm_undefined_error = re.escape("0^0 is undefined")
_avm_shift_right_too_big = "shr arg too big"
_avm_shift_left_too_big = "shl arg too big"


def _avm_overflow_error(op: str) -> str:
    return re.escape(f"'{op} overflowed'")


def _avm_pow_overflow_error(a: int, b: int) -> str:
    return re.escape(f"'{a}^{b} overflow'")


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_unary_plus(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert +UInt64(value) == value


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_bool(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert bool(UInt64(value)) == bool(value)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT64),
        (1, 0),
        (1, 1),
        (1, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
@pytest.mark.parametrize(
    "op_name",
    [
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
    ],
)
def test_uint64_comparison(get_avm_result: AVMInvoker, op_name: str, a: int, b: int) -> None:
    avm_result = get_avm_result(f"verify_uint64_{op_name}", a=a, b=b)
    op = getattr(operator, op_name)

    assert avm_result == op(UInt64(a), UInt64(b))
    assert avm_result == op(UInt64(a), b)
    assert avm_result == op(a, UInt64(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, MAX_UINT64),
        (MAX_UINT64, 0),
        (1, 0),
        (0, 1),
        (1, 1),
        (1, MAX_UINT64 - 1),
        (MAX_UINT64 - 1, 1),
    ],
)
def test_uint64_addition(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_add", a=a, b=b)
    assert avm_result == UInt64(a) + UInt64(b)
    assert avm_result == UInt64(a) + b
    assert avm_result == a + UInt64(b)
    i = UInt64(a)
    i += b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 1),
        (1, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_uint64_addition_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error("+")):
        get_avm_result("verify_uint64_add", a=a, b=b)

    with pytest.raises(OverflowError):
        UInt64(a) + UInt64(b)

    with pytest.raises(OverflowError):
        UInt64(a) + b

    with pytest.raises(OverflowError):
        a + UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (MAX_UINT64, 0),
        (MAX_UINT64, 1),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_uint64_subtraction(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_sub", a=a, b=b)
    assert avm_result == UInt64(a) - UInt64(b)
    assert avm_result == UInt64(a) - b
    assert avm_result == a - UInt64(b)
    i = UInt64(a)
    i -= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (1, 2),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
    ],
)
def test_uint64_subtraction_underflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_underflow_error):
        get_avm_result("verify_uint64_sub", a=a, b=b)

    with pytest.raises(ArithmeticError, match=_underflow_error):
        UInt64(a) - UInt64(b)

    with pytest.raises(ArithmeticError, match=_underflow_error):
        UInt64(a) - b

    with pytest.raises(ArithmeticError, match=_underflow_error):
        a - UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (2, 2),
    ],
)
def test_uint64_multiplication(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_mul", a=a, b=b)
    assert avm_result == UInt64(a) * UInt64(b)
    assert avm_result == UInt64(a) * b
    assert avm_result == a * UInt64(b)
    i = UInt64(a)
    i *= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 2),
        (MAX_UINT64, MAX_UINT64),
        (MAX_UINT64 // 2, 3),
    ],
)
def test_uint64_multiplication_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error("*")):
        get_avm_result("verify_uint64_mul", a=a, b=b)

    with pytest.raises(OverflowError):
        UInt64(a) * UInt64(b)

    with pytest.raises(OverflowError):
        UInt64(a) * b

    with pytest.raises(OverflowError):
        a * UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 1),
        (MAX_UINT64, 2),
        (MAX_UINT64, MAX_UINT64),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (3, 2),
    ],
)
def test_uint64_division(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_div", a=a, b=b)
    assert avm_result == UInt64(a) // UInt64(b)
    assert avm_result == UInt64(a) // b
    assert avm_result == a // UInt64(b)
    i = UInt64(a)
    i //= b
    assert avm_result == i


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_zero_division(get_avm_result: AVMInvoker, value: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_division_error):
        get_avm_result("verify_uint64_div", a=value, b=0)

    with pytest.raises(ZeroDivisionError):
        UInt64(value) // UInt64(0)

    with pytest.raises(ZeroDivisionError):
        UInt64(value) // 0

    with pytest.raises(ZeroDivisionError):
        value // UInt64(0)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 1),
        (MAX_UINT64, 2),
        (MAX_UINT64, MAX_UINT64),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (3, 2),
    ],
)
def test_uint64_mod(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_mod", a=a, b=b)
    assert avm_result == UInt64(a) % UInt64(b)
    assert avm_result == UInt64(a) % b
    assert avm_result == a % UInt64(b)
    i = UInt64(a)
    i %= b
    assert avm_result == i


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_zero_mod(get_avm_result: AVMInvoker, value: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_mod_error):
        get_avm_result("verify_uint64_mod", a=value, b=0)

    with pytest.raises(ZeroDivisionError):
        UInt64(value) % UInt64(0)

    with pytest.raises(ZeroDivisionError):
        UInt64(value) % 0

    with pytest.raises(ZeroDivisionError):
        value % UInt64(0)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, 1),
        (1, 0),
        (1, MAX_UINT64),
        (MAX_UINT64, 0),
        (MAX_UINT64, 1),
        (3, 4),
        (2**31, 2),
    ],
)
def test_uint64_power(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_pow", a=a, b=b)
    assert avm_result == UInt64(a) ** UInt64(b)
    assert avm_result == UInt64(a) ** b
    assert avm_result == a ** UInt64(b)
    i = UInt64(a)
    i **= b
    assert avm_result == i


def test_uint64_power_undefined(get_avm_result: AVMInvoker) -> None:
    a = b = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_undefined_error):
        get_avm_result("verify_uint64_pow", a=a, b=b)

    with pytest.raises(ArithmeticError, match=_undefined_error):
        UInt64(a) ** UInt64(b)

    with pytest.raises(ArithmeticError, match=_undefined_error):
        UInt64(a) ** b

    with pytest.raises(ArithmeticError, match=_undefined_error):
        a ** UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 2),
        (2, 64),
        (2**32, 32),
    ],
)
def test_uint64_power_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_pow_overflow_error(a, b)):
        get_avm_result("verify_uint64_pow", a=a, b=b)

    with pytest.raises(OverflowError):
        UInt64(a) ** UInt64(b)

    with pytest.raises(OverflowError):
        UInt64(a) ** b

    with pytest.raises(OverflowError):
        a ** UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT64, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT64, 0),
        (42, MAX_UINT64),
        (MAX_UINT64, 42),
    ],
)
def test_uint64_bitwise_and(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_and", a=a, b=b)
    assert avm_result == UInt64(a) & UInt64(b)
    assert avm_result == UInt64(a) & b
    assert avm_result == a & UInt64(b)
    i = UInt64(a)
    i &= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT64, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT64, 0),
        (42, MAX_UINT64),
        (MAX_UINT64, 42),
    ],
)
def test_uint64_bitwise_or(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_or", a=a, b=b)
    assert avm_result == UInt64(a) | UInt64(b)
    assert avm_result == UInt64(a) | b
    assert avm_result == a | UInt64(b)
    i = UInt64(a)
    i |= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT64, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT64, 0),
        (42, MAX_UINT64),
        (MAX_UINT64, 42),
    ],
)
def test_uint64_bitwise_xor(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_xor", a=a, b=b)
    assert avm_result == UInt64(a) ^ UInt64(b)
    assert avm_result == UInt64(a) ^ b
    assert avm_result == a ^ UInt64(b)
    i = UInt64(a)
    i ^= b
    assert avm_result == i


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        42,
        MAX_UINT64,
    ],
)
def test_uint64_not(get_avm_result: AVMInvoker, value: int) -> None:
    avm_result = get_avm_result("verify_uint64_not", a=value)
    assert avm_result == ~UInt64(value)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (1, 63),
        (42, 42),
        (MAX_UINT64, 0),
        (MAX_UINT64, 1),
        (MAX_UINT64, 63),
    ],
)
def test_uint64_bitwise_shift_left(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_lshift", a=a, b=b)

    assert avm_result == UInt64(a) << UInt64(b)
    assert avm_result == a << UInt64(b)
    assert avm_result == UInt64(a) << b
    i = UInt64(a)
    i <<= b
    assert avm_result == i


def test_uint64_invalid_lshift(get_avm_result: AVMInvoker) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_left_too_big):
        get_avm_result("verify_uint64_lshift", a=a, b=64)

    with pytest.raises(ArithmeticError, match=_shift_error):
        UInt64(a) << 64

    with pytest.raises(ArithmeticError, match=_shift_error):
        UInt64(a) << UInt64(64)

    # this would be a compile error
    with pytest.raises(ValueError, match=_too_big64_error):
        MAX_UINT64 + 1 << UInt64(1)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (1, 63),
        (42, 42),
        (MAX_UINT64, 0),
        (MAX_UINT64, 1),
        (MAX_UINT64, 63),
    ],
)
def test_uint64_bitwise_shift_right(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_uint64_rshift", a=a, b=b)

    assert avm_result == UInt64(a) >> UInt64(b)
    assert avm_result == a >> UInt64(b)
    assert avm_result == UInt64(a) >> b
    i = UInt64(a)
    i >>= b
    assert avm_result == i


def test_uint64_invalid_rshift(get_avm_result: AVMInvoker) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_right_too_big):
        get_avm_result("verify_uint64_rshift", a=a, b=64)

    with pytest.raises(ArithmeticError, match=_shift_error):
        UInt64(a) >> 64

    with pytest.raises(ArithmeticError, match=_shift_error):
        UInt64(a) >> UInt64(64)

    # this would be a compile error
    with pytest.raises(ValueError, match=_too_big64_error):
        MAX_UINT64 + 1 << UInt64(1)
    with pytest.raises(ValueError, match=_too_big64_error):
        MAX_UINT64 + 1 >> UInt64(1)


# operations that are equivalent to compile time errors


@pytest.mark.parametrize(
    "value",
    [
        MAX_UINT64 + 1,
        MAX_UINT64 * 2,
    ],
)
def test_uint64_too_big(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    with pytest.raises(ValueError, match=_too_big64_error):
        UInt64(value)


@pytest.mark.parametrize(
    "value",
    [
        -1,
        -MAX_UINT64,
        -MAX_UINT64 * 2,
    ],
)
def test_uint64_negative(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    with pytest.raises(ValueError, match=_negative_value_error):
        UInt64(value)


def test_uint64_type_error() -> None:
    with pytest.raises(TypeError):
        UInt64(3.0)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        UInt64(0) + 3.0  # type: ignore[operator]


@pytest.mark.parametrize(
    "valid",
    [0, 1, MAX_UINT64],
)
@pytest.mark.parametrize(
    "invalid",
    [-1, MAX_UINT64 + 1],
)
@pytest.mark.parametrize(
    "op",
    [
        operator.add,
        operator.sub,
        operator.mul,
        operator.floordiv,
        operator.mod,
        operator.and_,
        operator.or_,
        operator.xor,
        operator.lt,
        operator.le,
        operator.gt,
        operator.ge,
        operator.eq,
        operator.ne,
    ],
)
def test_uint64_invalid_pairs(
    valid: int, invalid: int, op: Callable[[object, object], object]
) -> None:
    valid_uint64 = UInt64(valid)
    invalid_uint64_error = f"({_negative_value_error}|{_too_big64_error})"
    with pytest.raises(ValueError, match=invalid_uint64_error):
        op(valid_uint64, invalid)

    with pytest.raises(ValueError, match=invalid_uint64_error):
        op(invalid, valid_uint64)


# NON AVM functionality
# these don't have an AVM equivalent, but are very useful when executing in a python context


def test_uint64_str() -> None:
    value = 42

    assert str(UInt64(value)) == str(value)
    assert repr(UInt64(value)) == f"{value}u"
