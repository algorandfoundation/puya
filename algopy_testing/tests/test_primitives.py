# from algopy import UInt64, Bytes, String, BigUInt
# from algopy_testing.primitives import UInt64 as TestUInt64, Bytes as TestBytes, String as TestString, BigUInt as TestBigUInt

import algokit_utils
import pytest
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from hypothesis import given, example
import algosdk
from algopy import UInt64, MAX_UINT64
from algopy.error.uint64 import UInt64OverflowError, UInt64UnderflowError
from tests.artifacts.PrimitiveOps.client import PrimitiveOpsContractClient
import hypothesis.strategies as st

MAX_UINT64_SHIFT = 64


@pytest.fixture(scope="session")
def primitive_ops_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> PrimitiveOpsContractClient:
    """
    Fixture for the PrimitiveOpsContractClient.
    """

    config.configure(
        debug=True,
        # trace_all=True,
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


@given(st.integers(min_value=MAX_UINT64 + 1))
@example(MAX_UINT64 + 1)
@example(2**128 - 1) # max limit for overflow scenarios
def test_uint64_overflow(primitive_ops_client: PrimitiveOpsContractClient, value: int):
    """
    Test that the AVM and direct implementation of UInt64 raise an error when
    given a value greater than the maximum value for UInt64.
    """
    
    # Test against the AVM
    with pytest.raises(algosdk.error.ABIEncodingError):
        primitive_ops_client.verify_uint64_init(value=value)

    # Test against the direct implementation
    with pytest.raises(UInt64OverflowError):
        UInt64(value)


@given(st.integers(max_value=-1))
@example(-1)
@example(-2**64) # max limit for underflow scenarios
def test_uint64_underflow(primitive_ops_client: PrimitiveOpsContractClient, value: int):
    """Test that underflow exceptions are raised for invalid negative values."""
    
    # Test against the AVM code 
    with pytest.raises(algosdk.error.ABIEncodingError):
        primitive_ops_client.verify_uint64_init(value=value)

    # Test against the direct implementation
    with pytest.raises(UInt64UnderflowError):
        UInt64(value)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_addition(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the addition operation for UInt64 instances."""
    if a + b > MAX_UINT64:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_add(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_add(a=a, b=b)
        assert result.return_value == UInt64(a) + UInt64(b)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_subtraction(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the subtraction operation for UInt64 instances."""
    if a - b < 0:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_sub(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_sub(a=a, b=b)
        assert result.return_value == UInt64(a) - UInt64(b)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_multiplication(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the multiplication operation for UInt64 instances."""
    if a * b > MAX_UINT64:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_mul(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_mul(a=a, b=b)
        assert result.return_value == UInt64(a) * UInt64(b)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
@example(10, 0)  # Explicit example to test division by zero
def test_uint64_division(primitive_ops_client: PrimitiveOpsContractClient, a, b):
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


@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
@example(1, 0)
def test_uint64_modulus(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the modulus operation for UInt64 instances."""
    if b == 0:
        with pytest.raises(algokit_utils.LogicError, match="% 0"):
            result = primitive_ops_client.verify_uint64_mod(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_mod(a=a, b=b)
        assert result.return_value == UInt64(a) % UInt64(b) 

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=64))
def test_uint64_power(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the power operation for UInt64 instances."""
    if a ** b > MAX_UINT64 or a == b == 0:
        with pytest.raises(algokit_utils.LogicError):
            result = primitive_ops_client.verify_uint64_pow(a=a, b=b)
    else:
        result = primitive_ops_client.verify_uint64_pow(a=a, b=b)
        assert result.return_value == UInt64(a) ** UInt64(b)


@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_bitwise_and(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the bitwise and operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_and(a=a, b=b)
    assert result.return_value == UInt64(a) & UInt64(b)


@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_bitwise_or(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the bitwise or operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_or(a=a, b=b)
    assert result.return_value == UInt64(a) | UInt64(b)


@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_bitwise_xor(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the bitwise xor operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_xor(a=a, b=b)
    assert result.return_value == UInt64(a) ^ UInt64(b)

@given(st.integers(min_value=0, max_value=MAX_UINT64))
def test_uint64_bitwise_not(primitive_ops_client: PrimitiveOpsContractClient, a):
    """Test the bitwise not operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_not(a=a)
    assert result.return_value == UInt64(MAX_UINT64 - a)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64_SHIFT))
def test_uint64_bitwise_shift_left(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the bitwise shift left operation for UInt64 instances."""
    result = primitive_ops_client.verify_uint64_lshift(a=a, b=b)
    assert result.return_value == UInt64(a) << UInt64(b)

@given(st.integers(min_value=0, max_value=MAX_UINT64), st.integers(min_value=0, max_value=MAX_UINT64_SHIFT))
def test_uint64_bitwise_shift_right(primitive_ops_client: PrimitiveOpsContractClient, a, b):
    """Test the bitwise shift right operation for UInt64 instances."""
    if b >= MAX_UINT64_SHIFT:
        with pytest.raises(algokit_utils.LogicError, match="shr arg too big"):
            result = primitive_ops_client.verify_uint64_rshift(a=a, b=b)
        with pytest.raises(algosdk.error.ABIEncodingError):
            UInt64(a) >> UInt64(b)
    else:
        result = primitive_ops_client.verify_uint64_rshift(a=a, b=b)
        assert result.return_value == UInt64(a) >> UInt64(b)

