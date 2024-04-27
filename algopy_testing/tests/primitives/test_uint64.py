import algokit_utils
import algosdk
import hypothesis.strategies as st
import pytest
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algopy import UInt64
from algopy.error.uint64 import UInt64OverflowError, UInt64UnderflowError
from algopy.primitives.constants import MAX_UINT64, MAX_UINT64_BIT_SHIFT
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from hypothesis import example, given, settings

from tests.artifacts.PrimitiveOps.client import PrimitiveOpsContractClient

EXAMPLES_PER_AVM_TEST = 5


@pytest.fixture(scope="session")
def primitive_ops_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> PrimitiveOpsContractClient:
    """
    Fixture for the PrimitiveOpsContractClient.
    """

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


@given(st.integers(min_value=MAX_UINT64 + 1, max_value=2 * MAX_UINT64))
def test_uint64_overflow(value: int) -> None:
    """
    Test that the python implementation of UInt64 raise an error when
    given a value greater than the maximum value for UInt64.

    NOTE: this scenario does not evaluate against AVM since algod validated parameters prior
    to passing for evaluation in AVM.
    Hence, it will always throw encoding errors (in cases of algosdk) OR http errors in case
    of direct invocation. Refer to other scenarios
    testing conditions when an overflow can happen as a result of a dynamic computation with
    in AVM.
    """

    # Test against the direct implementation
    with pytest.raises(UInt64OverflowError):
        UInt64(value)


@given(st.integers(min_value=-2 * MAX_UINT64, max_value=-1))
def test_uint64_underflow(value: int) -> None:
    """Test that underflow exceptions are raised for invalid negative values."""
    # Test against the direct implementation
    with pytest.raises(UInt64UnderflowError):
        UInt64(value)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_addition(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    """Test the addition operation for UInt64 instances."""
    if a + b > MAX_UINT64:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_add(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_add(a=a, b=b)
        assert result.return_value == UInt64(a) + UInt64(b)
        assert result.return_value == UInt64(a + b)
        assert result.return_value == UInt64(a) + b
        assert result.return_value == a + UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_subtraction(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the subtraction operation for UInt64 instances."""
    if a - b < 0:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_sub(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_sub(a=a, b=b)
        assert result.return_value == UInt64(a) - UInt64(b)
        assert result.return_value == UInt64(a - b)
        assert result.return_value == UInt64(a) - b
        assert result.return_value == a - UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_multiplication(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the multiplication operation for UInt64 instances."""
    if a * b > MAX_UINT64:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_mul(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_mul(a=a, b=b)
        assert result.return_value == UInt64(a) * UInt64(b)
        assert result.return_value == UInt64(a * b)
        assert result.return_value == UInt64(a) * b
        assert result.return_value == a * UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@example(10, 0)  # Explicit example to test division by zero
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_division(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    """Test that division by zero throws an error for UInt64 instances."""
    if b == 0:
        with pytest.raises(algokit_utils.LogicError, match="/ 0"):
            result = primitive_ops_client.verify_uint64_div(a=a, b=b)
    elif a / b > MAX_UINT64:
        with pytest.raises(algosdk.error.ABIEncodingError):
            result = primitive_ops_client.verify_uint64_div(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_div(a=a, b=b)
        assert result.return_value == UInt64(a) // UInt64(b)
        assert result.return_value == UInt64(a // b)
        assert result.return_value == UInt64(a) // b
        assert result.return_value == a // UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@example(1, 0)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_modulus(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    """Test the modulus operation for UInt64 instances."""
    if b == 0:
        with pytest.raises(algokit_utils.LogicError, match="% 0"):
            result = primitive_ops_client.verify_uint64_mod(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_mod(a=a, b=b)
        assert result.return_value == UInt64(a) % UInt64(b)
        assert result.return_value == UInt64(a % b)
        assert result.return_value == UInt64(a) % b
        assert result.return_value == a % UInt64(b)


@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=64))
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_power(primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int) -> None:
    """Test the power operation for UInt64 instances."""
    if a**b > MAX_UINT64 or a == b == 0:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_pow(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_pow(a=a, b=b)
        assert result.return_value == UInt64(a) ** UInt64(b)
        assert result.return_value == UInt64(a**b)
        assert result.return_value == UInt64(a) ** b
        assert result.return_value == a ** UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_and(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the bitwise and operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_and(a=a, b=b)
    assert result.return_value == UInt64(a) & UInt64(b)
    assert result.return_value == UInt64(a & b)
    assert result.return_value == UInt64(a) & b
    assert result.return_value == a & UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_or(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the bitwise or operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_or(a=a, b=b)
    assert result.return_value == UInt64(a) | UInt64(b)
    assert result.return_value == UInt64(a | b)
    assert result.return_value == UInt64(a) | b
    assert result.return_value == a | UInt64(b)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64)
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_xor(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the bitwise xor operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_xor(a=a, b=b)
    assert result.return_value == UInt64(a) ^ UInt64(b)
    assert result.return_value == UInt64(a ^ b)
    assert result.return_value == UInt64(a) ^ b
    assert result.return_value == a ^ UInt64(b)


@given(st.integers(min_value=0, max_value=MAX_UINT64))
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_not(primitive_ops_client: PrimitiveOpsContractClient, a: int) -> None:
    """Test the bitwise not operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_not(a=a)
    assert result.return_value == ~UInt64(a)


@given(
    st.integers(min_value=0, max_value=MAX_UINT64),
    st.integers(min_value=0, max_value=MAX_UINT64_BIT_SHIFT),
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_shift_left(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the bitwise shift left operation for UInt64 instances."""
    if b >= MAX_UINT64_BIT_SHIFT:
        with pytest.raises(algokit_utils.LogicError, match="shl arg too big"):
            result = primitive_ops_client.verify_uint64_lshift(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_lshift(a=a, b=b)
        assert result.return_value == UInt64(a) << UInt64(b)
        assert result.return_value == UInt64(a) << b


@given(
    st.integers(min_value=0, max_value=MAX_UINT64),
    st.integers(min_value=0, max_value=MAX_UINT64_BIT_SHIFT),
)
@settings(max_examples=EXAMPLES_PER_AVM_TEST)
def test_uint64_bitwise_shift_right(
    primitive_ops_client: PrimitiveOpsContractClient, a: int, b: int
) -> None:
    """Test the bitwise shift right operation for UInt64 instances."""
    if b >= MAX_UINT64_BIT_SHIFT:
        with pytest.raises(algokit_utils.LogicError, match="shr arg too big"):
            result = primitive_ops_client.verify_uint64_rshift(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_rshift(a=a, b=b)
        assert result.return_value == UInt64(a) >> UInt64(b)
        assert result.return_value == UInt64(a >> b)
        assert result.return_value == UInt64(a) >> b
