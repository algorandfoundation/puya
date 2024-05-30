import operator
import re
from collections.abc import Callable

import algokit_utils
import pytest
from algopy_testing.constants import MAX_UINT64, MAX_UINT512, UINT512_BYTES_LENGTH
from algopy_testing.primitives.biguint import BigUInt
from algopy_testing.primitives.uint64 import UInt64

from tests.common import AVMInvoker
from tests.util import int_to_bytes

_negative_value_error = "expected positive value"
_too_big512_error = re.escape(f"expected value <= {MAX_UINT512}")

_underflow_error = "- underflows"

_avm_overflow_error = "math attempted on large byte-array"
_avm_underflow_error = "byte math would have negative result"
_avm_zero_division_error = "division by zero"
_avm_zero_mod_error = "modulo by zero"


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
    avm_result = get_avm_result(f"verify_biguint_{op_name}", a=int_to_bytes(a), b=int_to_bytes(b))
    op = getattr(operator, op_name)

    assert avm_result == op(BigUInt(a), BigUInt(b))
    assert avm_result == op(BigUInt(a), b)
    assert avm_result == op(a, BigUInt(b))


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
@pytest.mark.parametrize(
    "pad",
    [
        "a",
        "b",
        "ab",
    ],
)
def test_biguint_comparison_from_bytes(
    get_avm_result: AVMInvoker, op_name: str, a: int, b: int, pad: str
) -> None:
    a_bytes = a.to_bytes(UINT512_BYTES_LENGTH, "big") if "a" in pad else int_to_bytes(a)
    b_bytes = b.to_bytes(UINT512_BYTES_LENGTH, "big") if "b" in pad else int_to_bytes(b)
    avm_result = get_avm_result(f"verify_biguint_{op_name}", a=a_bytes, b=b_bytes)
    op = getattr(operator, op_name)

    assert avm_result == op(BigUInt.from_bytes(a_bytes), BigUInt.from_bytes(b_bytes))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512 + 1, 1),
        (1, MAX_UINT512 + 1),
        (MAX_UINT512 + 1, MAX_UINT512),
        (MAX_UINT512, MAX_UINT512 + 1),
        (MAX_UINT512 + 1, MAX_UINT512 + 1),
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
def test_biguint_comparison_input_overflow(
    get_avm_result: AVMInvoker, op_name: str, a: int, b: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error):
        get_avm_result(f"verify_biguint_{op_name}", a=int_to_bytes(a), b=int_to_bytes(b))

    op = getattr(operator, op_name)
    with pytest.raises(ValueError, match=_too_big512_error):
        op(BigUInt(a), BigUInt(b))

    with pytest.raises(ValueError, match=_too_big512_error):
        op(BigUInt(a), b)

    with pytest.raises(ValueError, match=_too_big512_error):
        op(a, BigUInt(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT64),
        (1, 0),
        (1, 1),
        (1, MAX_UINT64),
        (MAX_UINT512, MAX_UINT64),
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
def test_biguint_comparison_uint64(
    get_avm_result: AVMInvoker, op_name: str, a: int, b: int
) -> None:
    avm_result = get_avm_result(f"verify_biguint_{op_name}_uint64", a=int_to_bytes(a), b=b)
    op = getattr(operator, op_name)
    assert avm_result == op(BigUInt(a), UInt64(b))
    if a <= MAX_UINT64:
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
    avm_result = get_avm_result("verify_biguint_add", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) + BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) + b).bytes
    assert avm_result == (a + BigUInt(b)).bytes
    i = BigUInt(a)
    i += b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, MAX_UINT64),
        (MAX_UINT512, 0),
        (1, 0),
        (0, 1),
        (1, 1),
        (10, MAX_UINT64),
        (MAX_UINT512 - MAX_UINT64, MAX_UINT64),
    ],
)
def test_biguint_addition_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_add_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) + UInt64(b)).bytes
    assert avm_result == (UInt64(b) + BigUInt(a)).bytes

    i = BigUInt(a)
    i += UInt64(b)
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (1, MAX_UINT512),
        (MAX_UINT512, MAX_UINT512),
    ],
)
def test_biguint_addition_result_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_add", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) + BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) + b).bytes
    assert avm_result == (a + BigUInt(b)).bytes
    i = BigUInt(a)
    i += b
    assert avm_result == i.bytes


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
        get_avm_result("verify_biguint_add", a=int_to_bytes(a), b=int_to_bytes(b))

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) + BigUInt(b)

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) + b

    with pytest.raises(ValueError, match=_too_big512_error):
        a + BigUInt(b)


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
    avm_result = get_avm_result("verify_biguint_sub", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) - BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) - b).bytes
    assert avm_result == (a - BigUInt(b)).bytes
    i = BigUInt(a)
    i -= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (MAX_UINT512, 0),
        (MAX_UINT512, 1),
        (MAX_UINT512, MAX_UINT64),
    ],
)
def test_biguint_subtraction_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_sub_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) - UInt64(b)).bytes
    if a <= MAX_UINT64:
        assert avm_result == (UInt64(a) - BigUInt(b)).bytes
    i = BigUInt(a)
    i -= UInt64(b)
    assert avm_result == i.bytes


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
        get_avm_result("verify_biguint_sub", a=int_to_bytes(a), b=int_to_bytes(b))

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
        get_avm_result("verify_biguint_sub", a=int_to_bytes(a), b=int_to_bytes(b))

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) - BigUInt(b)

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) - b

    with pytest.raises(ValueError, match=_too_big512_error):
        a - BigUInt(b)


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
    avm_result = get_avm_result("verify_biguint_mul", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) * BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) * b).bytes
    assert avm_result == (a * BigUInt(b)).bytes
    i = BigUInt(a)
    i *= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (2, MAX_UINT64),
    ],
)
def test_biguint_multiplication_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_mul_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) * UInt64(b)).bytes
    assert avm_result == (UInt64(b) * BigUInt(a)).bytes
    i = BigUInt(a)
    i *= UInt64(b)
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT512),
        (MAX_UINT512 // 2, 3),
    ],
)
def test_biguint_multiplication_overflow(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_mul", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) * BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) * b).bytes
    assert avm_result == (a * BigUInt(b)).bytes
    i = BigUInt(a)
    i *= b
    assert avm_result == i.bytes


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
        get_avm_result("verify_biguint_mul", a=int_to_bytes(a), b=int_to_bytes(b))

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) * BigUInt(b)

    with pytest.raises(ValueError, match=_too_big512_error):
        BigUInt(a) * b

    with pytest.raises(ValueError, match=_too_big512_error):
        a * BigUInt(b)


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
    avm_result = get_avm_result("verify_biguint_div", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) // BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) // b).bytes
    assert avm_result == (a // BigUInt(b)).bytes
    i = BigUInt(a)
    i //= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (3, 2),
    ],
)
def test_biguint_division_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_div_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) // UInt64(b)).bytes
    if a <= MAX_UINT64:
        assert avm_result == (UInt64(a) // BigUInt(b)).bytes
    i = BigUInt(a)
    i //= UInt64(b)
    assert avm_result == i.bytes


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
        get_avm_result("verify_biguint_div", a=int_to_bytes(value), b=int_to_bytes(0))

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
    avm_result = get_avm_result("verify_biguint_mod", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) % BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) % b).bytes
    assert avm_result == (a % BigUInt(b)).bytes
    i = BigUInt(a)
    i %= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT512, 1),
        (MAX_UINT512, 2),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
        (3, 2),
    ],
)
def test_biguint_mod_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_mod_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) % UInt64(b)).bytes
    if a <= MAX_UINT64:
        assert avm_result == (UInt64(a) % BigUInt(b)).bytes
    i = BigUInt(a)
    i %= UInt64(b)
    assert avm_result == i.bytes


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
        get_avm_result("verify_biguint_mod", a=int_to_bytes(value), b=int_to_bytes(0))

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
    avm_result = get_avm_result("verify_biguint_and", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) & BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) & b).bytes
    assert avm_result == (a & BigUInt(b)).bytes
    i = BigUInt(a)
    i &= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT64),
        (MAX_UINT512, 0),
        (42, MAX_UINT64),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_and_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_and_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) & UInt64(b)).bytes
    if a <= MAX_UINT64:
        assert avm_result == (UInt64(a) & BigUInt(b)).bytes
    i = BigUInt(a)
    i &= UInt64(b)
    assert avm_result == i.bytes


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
    avm_result = get_avm_result("verify_biguint_or", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) | BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) | b).bytes
    assert avm_result == (a | BigUInt(b)).bytes
    i = BigUInt(a)
    i |= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT512, 0),
        (42, MAX_UINT64),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_or_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_or_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) | UInt64(b)).bytes
    assert avm_result == (UInt64(b) | BigUInt(a)).bytes
    i = BigUInt(a)
    i |= UInt64(b)
    assert avm_result == i.bytes


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
    avm_result = get_avm_result("verify_biguint_xor", a=int_to_bytes(a), b=int_to_bytes(b))
    assert avm_result == (BigUInt(a) ^ BigUInt(b)).bytes
    assert avm_result == (BigUInt(a) ^ b).bytes
    assert avm_result == (a ^ BigUInt(b)).bytes
    i = BigUInt(a)
    i ^= b
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT512, 0),
        (42, MAX_UINT64),
        (MAX_UINT512, 42),
    ],
)
def test_biguint_bitwise_xor_uint64(get_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_avm_result("verify_biguint_xor_uint64", a=int_to_bytes(a), b=b)
    assert avm_result == (BigUInt(a) ^ UInt64(b)).bytes
    assert avm_result == (UInt64(b) ^ BigUInt(a)).bytes
    i = BigUInt(a)
    i ^= UInt64(b)
    assert avm_result == i.bytes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (MAX_UINT512, MAX_UINT64),
        (0, MAX_UINT64),
        (MAX_UINT512, 0),
        (42, MAX_UINT64),
        (MAX_UINT512, 42),
    ],
)
@pytest.mark.parametrize("op_name", ["add", "mul"])
def test_bytes_prefix(get_avm_result: AVMInvoker, a: int, b: int, op_name: str) -> None:
    a_bytes = int.to_bytes(a, UINT512_BYTES_LENGTH)
    b_bytes = int.to_bytes(b, UINT512_BYTES_LENGTH)
    avm_result = get_avm_result(f"verify_biguint_{op_name}", a=a_bytes, b=b_bytes)
    op = getattr(operator, op_name)
    assert avm_result == op(BigUInt.from_bytes(a_bytes), BigUInt.from_bytes(b_bytes)).bytes


# operations that are equivalent to compile time errors


@pytest.mark.parametrize(
    "value",
    [
        MAX_UINT512 + 1,
        MAX_UINT512 * 2,
    ],
)
def test_biguint_too_big(value: int) -> None:
    a = BigUInt(value)
    assert a.bytes == int_to_bytes(value)
    assert a.value == value

    with pytest.raises(ValueError, match=_too_big512_error):
        a & 1

    with pytest.raises(ValueError, match=_too_big512_error):
        +a  # noqa: B018


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
