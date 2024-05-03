import operator
import random
import re
import typing
from collections.abc import Callable
from pathlib import Path

import algokit_utils
import pytest
from algokit_utils import ApplicationClient, get_localnet_default_account
from algokit_utils.config import config
from algopy import UInt64
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

MAX_UINT64 = 2**64 - 1
MAX_UINT512 = 2**512 - 1
ARTIFACTS_DIR = Path(__file__).parent / ".." / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "PrimitiveOps" / "data" / "PrimitiveOpsContract.arc32.json"

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


@pytest.fixture(scope="session")
def primitive_ops_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> ApplicationClient:
    config.configure(
        debug=True,
    )

    client = ApplicationClient(
        algod_client,
        APP_SPEC,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    return client


class AVMInvoker(typing.Protocol):

    def __call__(self, method: str, **kwargs: typing.Any) -> object: ...


@pytest.fixture(scope="module")
def get_avm_result(primitive_ops_client: ApplicationClient) -> AVMInvoker:

    def wrapped(method: str, **kwargs: typing.Any) -> object:
        return primitive_ops_client.call(
            method,
            transaction_parameters={
                # random note avoids duplicate txn if tests are running concurrently
                "note": random.randbytes(8),  # noqa: S311
            },
            **kwargs,
        ).return_value

    return wrapped


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


def test_uint64_power_undefined(get_avm_result: AVMInvoker) -> None:
    a = b = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_undefined_error):
        get_avm_result("verify_uint64_pow", a=a, b=b)

    with pytest.raises(ValueError, match=_undefined_error):
        UInt64(a) ** UInt64(b)

    with pytest.raises(ValueError, match=_undefined_error):
        UInt64(a) ** b

    with pytest.raises(ValueError, match=_undefined_error):
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


def test_uint64_invalid_lshift(get_avm_result: AVMInvoker) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_left_too_big):
        get_avm_result("verify_uint64_lshift", a=a, b=64)

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) << 64

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) << UInt64(64)

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


def test_uint64_invalid_rshift(get_avm_result: AVMInvoker) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_right_too_big):
        get_avm_result("verify_uint64_rshift", a=a, b=64)

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) >> 64

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) >> UInt64(64)

    with pytest.raises(ValueError, match=_too_big64_error):
        MAX_UINT64 + 1 >> UInt64(1)


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


def test_uint64_index() -> None:
    # TODO: test indexing once we have a type to index
    pass


def test_uint64_str() -> None:
    value = 42
    # these don't have an AVM equivalent, but are very useful when executing in a python context
    assert str(UInt64(value)) == str(value)
    assert repr(UInt64(value)) == f"{value}u"


def test_uint64_type_error() -> None:
    with pytest.raises(TypeError):
        UInt64(3.0)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        UInt64(0) + 3.0  # type: ignore[operator]
