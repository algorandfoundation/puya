import operator
import re
from collections.abc import Callable

import algokit_utils
import pytest
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algopy import UInt64
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from tests.artifacts.PrimitiveOps.client import PrimitiveOpsContractClient

MAX_UINT64 = 2**64 - 1

_negative_value_error = "expected positive value"
_too_big_error = re.escape(f"expected value <= {MAX_UINT64}")
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
) -> PrimitiveOpsContractClient:
    config.configure(
        debug=True,
    )

    client = PrimitiveOpsContractClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    return client


@pytest.mark.parametrize(
    "value",
    [
        MAX_UINT64 + 1,
        MAX_UINT64 * 2,
    ],
)
def test_uint64_too_big(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    with pytest.raises(ValueError, match=_too_big_error):
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
def test_uint64_addition(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    result = primitive_ops_client.verify_uint64_add(a=a, b=b)
    assert result.return_value == UInt64(a) + UInt64(b)
    assert result.return_value == UInt64(a) + b
    assert result.return_value == a + UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 1),
        (1, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_uint64_addition_overflow(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error("+")):
        primitive_ops_client.verify_uint64_add(a=a, b=b)

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
def test_uint64_subtraction(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_sub(a=a, b=b)
    assert result.return_value == UInt64(a) - UInt64(b)
    assert result.return_value == UInt64(a) - b
    assert result.return_value == a - UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (1, 2),
        (0, MAX_UINT64),
        (1, MAX_UINT64),
    ],
)
def test_uint64_subtraction_underflow(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_underflow_error):
        primitive_ops_client.verify_uint64_sub(a=a, b=b)

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
def test_uint64_multiplication(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_mul(a=a, b=b)
    assert result.return_value == UInt64(a) * UInt64(b)
    assert result.return_value == UInt64(a) * b
    assert result.return_value == a * UInt64(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 2),
        (MAX_UINT64, MAX_UINT64),
        (MAX_UINT64 // 2, 3),
    ],
)
def test_uint64_multiplication_overflow(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_overflow_error("*")):
        primitive_ops_client.verify_uint64_mul(a=a, b=b)

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
def test_uint64_division(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    result = primitive_ops_client.verify_uint64_div(a=a, b=b)
    assert result.return_value == UInt64(a) // UInt64(b)
    assert result.return_value == UInt64(a) // b
    assert result.return_value == a // UInt64(b)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_zero_division(
    primitive_ops_client: PrimitiveOpsContractClient, value: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_division_error):
        primitive_ops_client.verify_uint64_div(a=value, b=0)

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
def test_uint64_mod(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    result = primitive_ops_client.verify_uint64_mod(a=a, b=b)
    assert result.return_value == UInt64(a) % UInt64(b)
    assert result.return_value == UInt64(a) % b
    assert result.return_value == a % UInt64(b)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        MAX_UINT64,
    ],
)
def test_uint64_zero_mod(primitive_ops_client: PrimitiveOpsContractClient, value: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_zero_mod_error):
        primitive_ops_client.verify_uint64_mod(a=value, b=0)

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
def test_uint64_power(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    result = primitive_ops_client.verify_uint64_pow(a=a, b=b)
    assert result.return_value == UInt64(a) ** UInt64(b)
    assert result.return_value == UInt64(a) ** b
    assert result.return_value == a ** UInt64(b)


def test_uint64_power_undefined(primitive_ops_client: PrimitiveOpsContractClient) -> None:
    a = b = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_undefined_error):
        primitive_ops_client.verify_uint64_pow(a=a, b=b)

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
def test_uint64_power_overflow(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_avm_pow_overflow_error(a, b)):
        primitive_ops_client.verify_uint64_pow(a=a, b=b)

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
def test_uint64_bitwise_and(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_and(a=a, b=b)
    assert result.return_value == UInt64(a) & UInt64(b)
    assert result.return_value == UInt64(a) & b
    assert result.return_value == a & UInt64(b)


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
def test_uint64_bitwise_or(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_or(a=a, b=b)
    assert result.return_value == UInt64(a) | UInt64(b)
    assert result.return_value == UInt64(a) | b
    assert result.return_value == a | UInt64(b)


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
def test_uint64_bitwise_xor(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_xor(a=a, b=b)
    assert result.return_value == UInt64(a) ^ UInt64(b)
    assert result.return_value == UInt64(a) ^ b
    assert result.return_value == a ^ UInt64(b)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        42,
        MAX_UINT64,
    ],
)
def test_uint64_not(primitive_ops_client: PrimitiveOpsContractClient, value: int) -> None:
    result = primitive_ops_client.verify_uint64_not(a=value)
    assert result.return_value == ~UInt64(value)


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
def test_uint64_bitwise_shift_left(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_lshift(a=a, b=b)

    assert result.return_value == UInt64(a) << UInt64(b)
    assert result.return_value == a << UInt64(b)
    assert result.return_value == UInt64(a) << b


def test_uint64_invalid_lshift(primitive_ops_client: PrimitiveOpsContractClient) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_left_too_big):
        primitive_ops_client.verify_uint64_lshift(a=a, b=64)

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) << 64

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) << UInt64(64)

    with pytest.raises(ValueError, match=_too_big_error):
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
def test_uint64_bitwise_shift_right(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    result = primitive_ops_client.verify_uint64_rshift(a=a, b=b)

    assert result.return_value == UInt64(a) >> UInt64(b)
    assert result.return_value == a >> UInt64(b)
    assert result.return_value == UInt64(a) >> b


def test_uint64_invalid_rshift(primitive_ops_client: PrimitiveOpsContractClient) -> None:
    a = 0
    with pytest.raises(algokit_utils.LogicError, match=_avm_shift_right_too_big):
        primitive_ops_client.verify_uint64_rshift(a=a, b=64)

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) >> 64

    with pytest.raises(ValueError, match=_shift_error):
        UInt64(a) >> UInt64(64)

    with pytest.raises(ValueError, match=_too_big_error):
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
    ],
)
def test_uint64_invalid_pairs(
    valid: int, invalid: int, op: Callable[[object, object], object]
) -> None:
    valid_uint64 = UInt64(valid)
    invalid_uint64_error = f"({_negative_value_error}|{_too_big_error})"
    with pytest.raises(ValueError, match=invalid_uint64_error):
        op(valid_uint64, invalid)

    with pytest.raises(ValueError, match=invalid_uint64_error):
        op(invalid, valid_uint64)
