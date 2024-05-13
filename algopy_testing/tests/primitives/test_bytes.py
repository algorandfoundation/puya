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
    ("a", "b"),
    [
        (b"", b""),
        (b"1", b""),
        (b"", b"1"),
        (b"1", b"1"),
        # throws "application args total length too long, max len 2048 bytes" error
        # (b"", b"0" * MAX_BYTES_SIZE),
        # (b"0" * MAX_BYTES_SIZE, b""),
        # (b"1", b"0" * (MAX_BYTES_SIZE - 1)),
        # (b"0" * (MAX_BYTES_SIZE - 1), 1),
    ],
)
def test_bytes_addition(get_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_avm_result("verify_bytes_add", a=a, b=b)
    assert avm_result == Bytes(a) + Bytes(b)
    assert avm_result == Bytes(a) + b
    assert avm_result == a + Bytes(b)
    i = Bytes(a)
    i += b
    assert avm_result == i
