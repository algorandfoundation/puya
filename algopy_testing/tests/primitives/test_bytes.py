import base64

import algokit_utils
import pytest
from algopy_testing.constants import MAX_BYTES_SIZE
from algopy_testing.primitives.bytes import Bytes

from tests.common import AVMInvoker
from tests.util import get_sha256_hash, int_to_bytes


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


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"0", b"0"),
        (b"", b""),
        (b"11", b"11"),
        (b"011", b"11"),
        (b"11", b"001"),
        (b"", b"00"),
    ],
)
def test_bytes_bitwise_eq(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_eq", a=a, b=b)
    assert avm_result == (Bytes(a) == Bytes(b))
    assert avm_result == (Bytes(a) == b)
    assert avm_result == (a == Bytes(b))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"0", b"0"),
        (b"", b""),
        (b"11", b"11"),
        (b"011", b"11"),
        (b"11", b"001"),
        (b"", b"00"),
    ],
)
def test_bytes_bitwise_ne(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_ne", a=a, b=b)
    assert avm_result == (Bytes(a) != Bytes(b))
    assert avm_result == (Bytes(a) != b)
    assert avm_result == (a != Bytes(b))


# NON AVM functionality
# these don't have an AVM equivalent, but are very useful when executing in a python context


def test_bytes_str() -> None:
    value = b"hello, world"

    assert str(Bytes(value)) == str(value)
    assert repr(Bytes(value)) == repr(value)


def test_bytes_from_encoded_string() -> None:
    base32_str = "74======"
    assert Bytes.from_base32(base32_str) == base64.b32decode(base32_str)

    base64_str = "RkY="
    assert Bytes.from_base64(base64_str) == base64.b64decode(base64_str)

    hex_str = "FF"
    assert Bytes.from_hex(hex_str) == base64.b16decode(hex_str)


@pytest.mark.parametrize("value", [b"hello, world", b"", b"0110", b"0" * MAX_BYTES_SIZE])
def test_bytes_len(value: bytes) -> None:
    assert len(Bytes(value)) == len(value)
    assert Bytes(value).length == len(value)


@pytest.mark.parametrize("value", [b"hello, world", b"", b"0110", b"0" * MAX_BYTES_SIZE])
def test_bytes_iter(value: bytes) -> None:
    for x1, x2 in zip(iter(Bytes(value)), iter(value), strict=True):
        assert x1 == int_to_bytes(x2)


@pytest.mark.parametrize("value", [b"hello, world", b"", b"0110", b"0" * MAX_BYTES_SIZE])
def test_bytes_reversed(value: bytes) -> None:
    for x1, x2 in zip(reversed(Bytes(value)), reversed(value), strict=True):
        assert x1 == int_to_bytes(x2)


@pytest.mark.parametrize(
    "index",
    [
        0,
        slice(0, 2),
        11,
        slice(11, 12),
        slice(10, 13),
    ],
)
def test_bytes_index(index: int | slice) -> None:
    value = b"hello, world"
    if isinstance(index, slice):
        assert Bytes(value)[index] == value[index]
    else:
        assert Bytes(value)[index] == int_to_bytes(value[index])
