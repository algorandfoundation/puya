import operator
import re
from collections.abc import Callable

import algokit_utils
import pytest
from algopy import BigUInt, UInt64
from algopy.constants import MAX_UINT64, MAX_UINT512

from tests.primitives.conftest import AVMInvoker

_negative_value_error = "expected positive value"
_too_big512_error = re.escape(f"expected value <= {MAX_UINT512}")

_underflow_error = "- underflows"

_avm_overflow_error = "math attempted on large byte-array"
_avm_underflow_error = "byte math would have negative result"
_avm_zero_division_error = "division by zero"
_avm_zero_mod_error = "modulo by zero"


def _int_to_bytes(x: int) -> bytes:
    return x.to_bytes((x.bit_length() + 7) // 8, "big")


def _object_as_biguint(x: object) -> BigUInt | object:
    return BigUInt.from_bytes(x) if (isinstance(x, bytes)) else x


def _get_avm_result(
    get_avm_result: AVMInvoker, method: str, a: int, b: int | UInt64
) -> BigUInt | object:
    a_bytes = _int_to_bytes(a)
    if isinstance(b, UInt64):
        avm_result = get_avm_result(method, a=a_bytes, b=b.value)
    else:
        b_bytes = _int_to_bytes(b)
        avm_result = get_avm_result(method, a=a_bytes, b=b_bytes)
    return _object_as_biguint(avm_result)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT512,
    ],
)
def test_biguint_unary_plus(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert +BigUInt(value) == value


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT512,
    ],
)
def test_biguint_bool(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert bool(BigUInt(value)) == bool(value)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT512),
        (1, 0),
        (1, 1),
        (1, MAX_UINT512),
        (MAX_UINT512, MAX_UINT512),
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
def test_biguint_comparison(get_avm_result: AVMInvoker, op_name: str, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, f"verify_biguint_{op_name}", a, b)
    op = getattr(operator, op_name)

    assert avm_result == op(BigUInt(a), BigUInt(b))
    assert avm_result == op(BigUInt(a), b)
    assert avm_result == op(a, BigUInt(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (0, UInt64(1)),
        (0, UInt64(MAX_UINT64)),
        (1, UInt64(0)),
        (1, UInt64(1)),
        (1, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (MAX_UINT64, UInt64(MAX_UINT64)),
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
def test_biguint_comparison_uint64(
    get_avm_result: AVMInvoker, op_name: str, a: int, b: UInt64
) -> None:
    avm_result = _get_avm_result(get_avm_result, f"verify_biguint_{op_name}_uint64", a, b)
    op = getattr(operator, op_name)
    assert avm_result == op(BigUInt(a), b)
    if a < MAX_UINT64:
        assert avm_result == op(UInt64(a), BigUInt(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, MAX_UINT512),
        (MAX_UINT512, 0),
        (1, 0),
        (0, 1),
        (1, 1),
        (1, MAX_UINT512 - 1),
        (MAX_UINT512 - 1, 1),
    ],
)
def test_biguint_addition(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_add", a=a, b=b)
    assert avm_result == BigUInt(a) + BigUInt(b)
    assert avm_result == BigUInt(a) + b
    assert avm_result == a + BigUInt(b)
    i = BigUInt(a)
    i += b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (0, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(0)),
        (1, UInt64(0)),
        (0, UInt64(1)),
        (1, UInt64(1)),
        (10, UInt64(MAX_UINT64)),
        (MAX_UINT512 - MAX_UINT64, UInt64(MAX_UINT64)),
    ],
)
def test_biguint_addition_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_add_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) + b
    assert avm_result == b + BigUInt(a)
    i = BigUInt(a)
    i += b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (1, MAX_UINT512),
        (MAX_UINT512, MAX_UINT512),
    ],
)
def test_biguint_addition_result_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big512_error):
        _get_avm_result(get_avm_result, "verify_biguint_add", a, b)

    with pytest.raises(OverflowError):
        BigUInt(a) + BigUInt(b)

    with pytest.raises(OverflowError):
        BigUInt(a) + b

    with pytest.raises(OverflowError):
        a + BigUInt(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512 + 1, 1),
        (1, MAX_UINT512 + 1),
        (MAX_UINT512 + 1, MAX_UINT512 + 1),
    ],
)
def test_biguint_addition_input_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error):
        _get_avm_result(get_avm_result, "verify_biguint_add", a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (MAX_UINT512, 0),
        (MAX_UINT512, 1),
        (MAX_UINT512, MAX_UINT512),
    ],
)
def test_biguint_subtraction(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_sub", a=a, b=b)
    assert avm_result == BigUInt(a) - BigUInt(b)
    assert avm_result == BigUInt(a) - b
    assert avm_result == a - BigUInt(b)
    i = BigUInt(a)
    i -= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (1, UInt64(0)),
        (1, UInt64(1)),
        (MAX_UINT512, UInt64(0)),
        (MAX_UINT512, UInt64(1)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
    ],
)
def test_biguint_subtraction_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_sub_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) - b
    if a < MAX_UINT64:
        assert avm_result == UInt64(a) - BigUInt(b)
    i = BigUInt(a)
    i -= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (1, 2),
        (0, MAX_UINT512),
        (1, MAX_UINT512),
    ],
)
def test_biguint_subtraction_result_underflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_underflow_error):
        _get_avm_result(get_avm_result, "verify_biguint_sub", a, b)

    with pytest.raises(ArithmeticError, match=_underflow_error):
        BigUInt(a) - BigUInt(b)

    with pytest.raises(ArithmeticError, match=_underflow_error):
        BigUInt(a) - b

    with pytest.raises(ArithmeticError, match=_underflow_error):
        a - BigUInt(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512 + 1, 1),
        (1, MAX_UINT512 + 1),
        (MAX_UINT512 + 1, MAX_UINT512 + 1),
    ],
)
def test_biguint_subtraction_input_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error):
        _get_avm_result(get_avm_result, "verify_biguint_sub", a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT512),
        (1, MAX_UINT512),
        (2, 2),
    ],
)
def test_biguint_multiplication(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_mul", a, b)
    assert avm_result == BigUInt(a) * BigUInt(b)
    assert avm_result == BigUInt(a) * b
    assert avm_result == a * BigUInt(b)
    i = BigUInt(a)
    i *= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (0, UInt64(1)),
        (0, UInt64(MAX_UINT64)),
        (1, UInt64(MAX_UINT64)),
        (2, UInt64(MAX_UINT64)),
    ],
)
def test_biguint_multiplication_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_mul_uint64", a, b)
    assert avm_result == BigUInt(a) * b
    assert avm_result == b * BigUInt(a)
    i = BigUInt(a)
    i *= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT512),
        (MAX_UINT512 // 2, 3),
    ],
)
def test_biguint_multiplication_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big512_error):
        _get_avm_result(get_avm_result, "verify_biguint_mul", a=a, b=b)

    with pytest.raises(OverflowError):
        BigUInt(a) * BigUInt(b)

    with pytest.raises(OverflowError):
        BigUInt(a) * b

    with pytest.raises(OverflowError):
        a * BigUInt(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512 + 1, 2),
        (2, MAX_UINT512 + 1),
        (MAX_UINT512 + 1, MAX_UINT512 + 1),
    ],
)
def test_biguint_multiplication_input_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error):
        _get_avm_result(get_avm_result, "verify_biguint_mul", a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT512),
        (0, MAX_UINT512),
        (1, MAX_UINT512),
        (3, 2),
    ],
)
def test_biguint_division(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_div", a=a, b=b)
    assert avm_result == BigUInt(a) // BigUInt(b)
    assert avm_result == BigUInt(a) // b
    assert avm_result == a // BigUInt(b)
    i = BigUInt(a)
    i //= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, UInt64(1)),
        (MAX_UINT512, UInt64(2)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (0, UInt64(MAX_UINT64)),
        (1, UInt64(MAX_UINT64)),
        (3, UInt64(2)),
    ],
)
def test_biguint_division_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_div_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) // b
    if a < MAX_UINT64:
        assert avm_result == UInt64(a) // BigUInt(b)
    i = BigUInt(a)
    i //= b
    assert avm_result == i


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT512,
    ],
)
def test_biguint_zero_division(get_avm_result: AVMInvoker, value: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_division_error):
        _get_avm_result(get_avm_result, "verify_biguint_div", a=value, b=0)

    with pytest.raises(ZeroDivisionError):
        BigUInt(value) // BigUInt(0)

    with pytest.raises(ZeroDivisionError):
        BigUInt(value) // 0

    with pytest.raises(ZeroDivisionError):
        value // BigUInt(0)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT512),
        (1, MAX_UINT512),
        (3, 2),
    ],
)
def test_biguint_mod(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_mod", a=a, b=b)
    assert avm_result == BigUInt(a) % BigUInt(b)
    assert avm_result == BigUInt(a) % b
    assert avm_result == a % BigUInt(b)
    i = BigUInt(a)
    i %= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, UInt64(1)),
        (MAX_UINT512, UInt64(2)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (0, UInt64(MAX_UINT64)),
        (1, UInt64(MAX_UINT64)),
        (3, UInt64(2)),
    ],
)
def test_biguint_mod_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_mod_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) % b
    if a < MAX_UINT64:
        assert avm_result == UInt64(a) % BigUInt(b)
    i = BigUInt(a)
    i %= b
    assert avm_result == i


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT512,
    ],
)
def test_biguint_zero_mod(get_avm_result: AVMInvoker, value: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_mod_error):
        _get_avm_result(get_avm_result, "verify_biguint_mod", a=value, b=0)

    with pytest.raises(ZeroDivisionError):
        BigUInt(value) % BigUInt(0)

    with pytest.raises(ZeroDivisionError):
        BigUInt(value) % 0

    with pytest.raises(ZeroDivisionError):
        value % BigUInt(0)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT512),
        (0, MAX_UINT512),
        (MAX_UINT512, 0),
        (42, MAX_UINT512),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_and(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_and", a=a, b=b)
    assert avm_result == BigUInt(a) & BigUInt(b)
    assert avm_result == BigUInt(a) & b
    assert avm_result == a & BigUInt(b)
    i = BigUInt(a)
    i &= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(0)),
        (42, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(42)),
    ],
)
def test_biguint_bitwise_and_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_and_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) & b
    i = BigUInt(a)
    i &= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT512),
        (0, MAX_UINT512),
        (MAX_UINT512, 0),
        (42, MAX_UINT512),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_or(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_or", a=a, b=b)
    assert avm_result == BigUInt(a) | BigUInt(b)
    assert avm_result == BigUInt(a) | b
    assert avm_result == a | BigUInt(b)
    i = BigUInt(a)
    i |= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (0, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(0)),
        (42, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(42)),
    ],
)
def test_biguint_bitwise_or_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_or_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) | b
    assert avm_result == b | BigUInt(a)
    i = BigUInt(a)
    i |= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT512),
        (0, MAX_UINT512),
        (MAX_UINT512, 0),
        (42, MAX_UINT512),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_xor(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_xor", a=a, b=b)
    assert avm_result == BigUInt(a) ^ BigUInt(b)
    assert avm_result == BigUInt(a) ^ b
    assert avm_result == a ^ BigUInt(b)
    i = BigUInt(a)
    i ^= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, UInt64(0)),
        (MAX_UINT512, UInt64(MAX_UINT64)),
        (0, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(0)),
        (42, UInt64(MAX_UINT64)),
        (MAX_UINT512, UInt64(42)),
    ],
)
def test_biguint_bitwise_xor_uint64(get_avm_result: AVMInvoker, a: int, b: UInt64) -> None:
    avm_result = _get_avm_result(get_avm_result, "verify_biguint_xor_uint64", a=a, b=b)
    assert avm_result == BigUInt(a) ^ b
    assert avm_result == b ^ BigUInt(a)
    i = BigUInt(a)
    i ^= b
    assert avm_result == i


# operations that are equivalent to compile time errors


@pytest.mark.parametrize(
    "value",
    [
        MAX_UINT512 + 1,
        MAX_UINT512 * 2,
    ],
)
def test_biguint_too_big(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(value)


@pytest.mark.parametrize(
    "value",
    [
        -1,
        -MAX_UINT512,
        -MAX_UINT512 * 2,
    ],
)
def test_biguint_negative(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    with pytest.raises(ValueError, match=_negative_value_error):
        BigUInt(value)


def test_biguint_type_error() -> None:
    with pytest.raises(TypeError):
        BigUInt(3.0)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        BigUInt(0) + 3.0  # type: ignore[operator]


@pytest.mark.parametrize(
    "valid",
    [0, 1, MAX_UINT512],
)
@pytest.mark.parametrize(
    "invalid",
    [-1, MAX_UINT512 + 1],
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
def test_biguint_invalid_pairs(
    valid: int, invalid: int, op: Callable[[object, object], object]
) -> None:
    valid_biguint = BigUInt(valid)
    invalid_biguint_error = f"({_negative_value_error}|{_too_big512_error})"
    with pytest.raises(ValueError, match=invalid_biguint_error):
        op(valid_biguint, invalid)

    with pytest.raises(ValueError, match=invalid_biguint_error):
        op(invalid, valid_biguint)


# NON AVM functionality
# these don't have an AVM equivalent, but are very useful when executing in a python context


def test_biguint_str() -> None:
    value = 42

    assert str(BigUInt(value)) == str(value)
    assert repr(BigUInt(value)) == f"{value}u"
