from hashlib import sha256

import algokit_utils
import pytest
from algopy._constants import MAX_BYTES_SIZE
from algopy.primitives.bytes import Bytes

from tests.primitives.conftest import AVMInvoker


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"1",
        b"0" * MAX_BYTES_SIZE,
    ],
)
def test_bytes_bool(value: bytes) -> None:
    # just test the implementation as there is no AVM equivalent
    assert bool(Bytes(value)) == bool(value)


@pytest.mark.parametrize(
    ("a", "b", "pad_a_size", "pad_b_size"),
    [
        (b"", b"", 0, 0),
        (b"1", b"", 0, 0),
        (b"", b"1", 0, 0),
        (b"1", b"1", 0, 0),
        (b"", b"0", 0, MAX_BYTES_SIZE - 1),
        (b"0", b"", MAX_BYTES_SIZE - 1, 0),
        (b"1", b"0", 0, MAX_BYTES_SIZE - 2),
        (b"1", b"0", MAX_BYTES_SIZE - 2, 0),
    ],
)
def test_bytes_addition(
    get_avm_result: AVMInvoker, a: bytes, b: bytes, pad_a_size: int, pad_b_size: int
) -> None:
    avm_result = get_avm_result(
        "verify_bytes_add", a=a, b=b, pad_a_size=pad_a_size, pad_b_size=pad_b_size
    )

    a = (b"\x00" * pad_a_size) + a
    b = (b"\x00" * pad_b_size) + b
    assert avm_result == get_sha256_hash(Bytes(a) + Bytes(b))
    assert avm_result == get_sha256_hash(Bytes(a) + b)
    assert avm_result == get_sha256_hash(a + Bytes(b))
    i = Bytes(a)
    i += b
    assert avm_result == get_sha256_hash(i)


@pytest.mark.parametrize(
    ("a", "b", "pad_a_size", "pad_b_size"),
    [
        (b"", b"", 1, MAX_BYTES_SIZE),
        (b"1", b"", 0, MAX_BYTES_SIZE),
        (b"", b"", MAX_BYTES_SIZE, MAX_BYTES_SIZE),
    ],
)
def test_bytes_addition_overflow(
    get_avm_result: AVMInvoker, a: bytes, b: bytes, pad_a_size: int, pad_b_size: int
) -> None:
    with pytest.raises(
        algokit_utils.LogicError, match="concat produced a too big \\(\\d+\\) byte-array"
    ):
        get_avm_result("verify_bytes_add", a=a, b=b, pad_a_size=pad_a_size, pad_b_size=pad_b_size)

    a = (b"\x00" * pad_a_size) + a
    b = (b"\x00" * pad_b_size) + b
    with pytest.raises(OverflowError):
        Bytes(a) + Bytes(b)

    with pytest.raises(OverflowError):
        Bytes(a) + b

    with pytest.raises(OverflowError):
        a + Bytes(b)


@pytest.mark.parametrize(
    ("value", "pad_size"),
    [
        (b"0", 0),
        (b"1", 0),
        (b"1010", 0),
        (b"11100", MAX_BYTES_SIZE - 5),
        (b"", MAX_BYTES_SIZE),
    ],
)
def test_bytes_not(get_avm_result: AVMInvoker, value: bytes, pad_size: int) -> None:
    avm_result = get_avm_result("verify_bytes_not", a=value, pad_size=pad_size)
    value = (b"\x00" * pad_size) + value
    assert avm_result == get_sha256_hash(~Bytes(value))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"0", b"0"),
        (b"001", b"11"),
        (b"100", b"11"),
        (b"00", b"111"),
        (b"11", b"001"),
        (b"", b"11"),
    ],
)
def test_bytes_bitwise_and(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_and", a=a, b=b)
    assert avm_result == Bytes(a) & Bytes(b)
    assert avm_result == Bytes(a) & b
    assert avm_result == a & Bytes(b)
    i = Bytes(a)
    i &= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"0", b"0"),
        (b"001", b"11"),
        (b"100", b"11"),
        (b"00", b"111"),
        (b"11", b"001"),
        (b"", b"11"),
    ],
)
def test_bytes_bitwise_or(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_or", a=a, b=b)
    assert avm_result == Bytes(a) | Bytes(b)
    assert avm_result == Bytes(a) | b
    assert avm_result == a | Bytes(b)
    i = Bytes(a)
    i |= b
    assert avm_result == i


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"0", b"0"),
        (b"001", b"11"),
        (b"100", b"11"),
        (b"00", b"111"),
        (b"11", b"001"),
        (b"", b"11"),
    ],
)
def test_bytes_bitwise_xor(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_xor", a=a, b=b)
    assert avm_result == Bytes(a) ^ Bytes(b)
    assert avm_result == Bytes(a) ^ b
    assert avm_result == a ^ Bytes(b)
    i = Bytes(a)
    i ^= b
    assert avm_result == i


def get_sha256_hash(v: Bytes) -> Bytes:
    return Bytes(sha256(v.value).digest())
