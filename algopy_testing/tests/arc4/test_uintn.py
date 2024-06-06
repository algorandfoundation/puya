import operator
import typing

import algokit_utils
import pytest
from algopy_testing import arc4
from algopy_testing.constants import ARC4_RETURN_PREFIX, MAX_UINT64, MAX_UINT512
from algopy_testing.primitives.bytes import Bytes

from tests.common import AVMInvoker
from tests.util import int_to_bytes


def _invalid_bytes_length_error(length: int) -> str:
    return f"value string must be in bytes and correspond to a uint{length}"


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        255,
    ],
)
def test_unintn_bool(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert bool(arc4.UInt8(value)) == bool(value)
    assert bool(arc4.UIntN[typing.Literal[24]](value)) == bool(value)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        255,
    ],
)
def test_unintn_bytes(value: int) -> None:
    # just test the implementation as there is no AVM equivalent
    assert arc4.UInt8(value).bytes == int_to_bytes(value, 1)
    assert arc4.UInt16(value).bytes == int_to_bytes(value, 2)
    assert arc4.UInt64(value).bytes == int_to_bytes(value, 8)
    assert arc4.UInt512(value).bytes == int_to_bytes(value, 64)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 1),
        (0, 255),
        (255, 255),
        (65535, 65535),
        (255, 65535),
        (MAX_UINT64, MAX_UINT64),
        (65535, 4294967295),
        (4294967295, MAX_UINT64),
        (MAX_UINT64, MAX_UINT512),
        (0, MAX_UINT512),
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
def test_uintn_comparison(get_avm_result: AVMInvoker, op_name: str, a: int, b: int) -> None:
    op = getattr(operator, op_name)

    a_type = "uintn" if a <= MAX_UINT64 else "biguintn"
    b_type = "uintn" if b <= MAX_UINT64 else "biguintn"
    avm_result = get_avm_result(
        f"verify_{a_type}_{b_type}_{op_name}", a=int_to_bytes(a), b=int_to_bytes(b)
    )

    result = op(
        arc4.UInt64(a) if a <= MAX_UINT64 else arc4.UInt512(a),
        arc4.UInt64(b) if b <= MAX_UINT64 else arc4.UInt512(b),
    )

    assert avm_result == result


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (255, 255),
        (2**32 - 1, 2**32 - 1),
        (2**32, None),
        (MAX_UINT64, None),
    ],
)
def test_uintn_overflow(get_avm_result: AVMInvoker, value: int, expected: int | None) -> None:
    if expected is None:
        with pytest.raises(algokit_utils.LogicError, match="assert failed"):
            get_avm_result("verify_uintn_init", a=int_to_bytes(value))
        with pytest.raises(ValueError, match=f"expected value <= {2**32-1}"):
            arc4.UInt32(value)
    else:
        avm_result = get_avm_result("verify_uintn_init", a=int_to_bytes(value))
        result = arc4.UInt32(value)
        assert avm_result == expected
        assert avm_result == result


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (255, 255),
        (MAX_UINT64, MAX_UINT64),
        (2**128, 2**128),
        (2**256 - 1, 2**256 - 1),
        (2**256, None),
        (MAX_UINT512, None),
    ],
)
def test_biguintn_overflow(get_avm_result: AVMInvoker, value: int, expected: int | None) -> None:
    if expected is None:
        with pytest.raises(algokit_utils.LogicError, match="assert failed"):
            get_avm_result("verify_biguintn_init", a=int_to_bytes(value))
        with pytest.raises(ValueError, match=f"expected value <= {2**256 - 1}"):
            arc4.UInt256(value)
    else:
        avm_result = get_avm_result("verify_biguintn_init", a=int_to_bytes(value))
        result = arc4.UInt256(value)
        assert avm_result == expected
        assert avm_result == result


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 4),
        int_to_bytes(255, 4),
        int_to_bytes(2**16, 4),
        int_to_bytes(2**32 - 1, 4),
        int_to_bytes(2**32 - 1),
    ],
)
def test_uintn_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    avm_result = get_avm_result("verify_uintn_from_bytes", a=value)
    result = arc4.UInt32.from_bytes(value)
    assert avm_result == result


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 1),
        int_to_bytes(0, 8),
        int_to_bytes(255, 2),
        int_to_bytes(2**32 - 1, 8),
    ],
)
def test_uintn_from_bytes_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(32)):
        get_avm_result("verify_uintn_from_bytes", a=value)

    result = arc4.UInt32.from_bytes(value)
    assert result == int.from_bytes(value)


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 32),
        int_to_bytes(255, 32),
        int_to_bytes(2**256 - 1, 32),
        int_to_bytes(2**256 - 1),
    ],
)
def test_biguintn_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    avm_result = get_avm_result("verify_biguintn_from_bytes", a=value)
    result = arc4.UInt256.from_bytes(value)
    assert avm_result == result


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 16),
        int_to_bytes(0, 40),
        int_to_bytes(2**128 - 1, 16),
        int_to_bytes(2**256 - 1, 40),
    ],
)
def test_biguintn_from_bytes_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(256)):
        get_avm_result("verify_biguintn_from_bytes", a=value)

    result = arc4.UInt256.from_bytes(value)
    assert result == int.from_bytes(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (int_to_bytes(0, 4), 0),
        (int_to_bytes(255, 4), 255),
        (int_to_bytes(2**16, 4), 2**16),
        (int_to_bytes(2**32 - 1, 4), 2**32 - 1),
    ],
)
def test_uintn_from_log(get_avm_result: AVMInvoker, value: bytes, expected: int) -> None:
    avm_result = get_avm_result("verify_uintn_from_log", a=ARC4_RETURN_PREFIX + value)
    result = arc4.UInt32.from_log(Bytes(ARC4_RETURN_PREFIX + value))
    assert avm_result == expected
    assert avm_result == result


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (int_to_bytes(255, 4), b""),
        (int_to_bytes(255, 4), b"\xff\x00\x01\x02"),
    ],
)
def test_uintn_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    with pytest.raises(algokit_utils.LogicError, match="assert failed"):
        get_avm_result("verify_uintn_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.UInt32.from_log(Bytes(prefix + value))


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 1),
        int_to_bytes(0, 8),
        int_to_bytes(255, 2),
        int_to_bytes(2**32 - 1, 8),
    ],
)
def test_uintn_from_log_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(32)):
        get_avm_result("verify_uintn_from_log", a=ARC4_RETURN_PREFIX + value)

    result = arc4.UInt32.from_log(Bytes(ARC4_RETURN_PREFIX + value))
    assert result == int.from_bytes(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (int_to_bytes(0, 32), 0),
        (int_to_bytes(255, 32), 255),
        (int_to_bytes(2**16, 32), 2**16),
        (int_to_bytes(2**256 - 1, 32), 2**256 - 1),
    ],
)
def test_biguintn_from_log(get_avm_result: AVMInvoker, value: bytes, expected: int) -> None:
    avm_result = get_avm_result("verify_biguintn_from_log", a=ARC4_RETURN_PREFIX + value)
    result = arc4.UInt256.from_log(Bytes(ARC4_RETURN_PREFIX + value))
    assert avm_result == expected
    assert avm_result == result


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (int_to_bytes(255, 32), b""),
        (int_to_bytes(255, 32), b"\xff\x00\x01\x02"),
    ],
)
def test_biguintn_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    with pytest.raises(algokit_utils.LogicError, match="assert failed"):
        get_avm_result("verify_biguintn_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.UInt256.from_log(Bytes(prefix + value))


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 16),
        int_to_bytes(0, 40),
        int_to_bytes(2**128 - 1, 16),
        int_to_bytes(2**256 - 1, 40),
    ],
)
def test_biguintn_from_log_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(256)):
        get_avm_result("verify_biguintn_from_log", a=ARC4_RETURN_PREFIX + value)

    result = arc4.UInt256.from_log(Bytes(ARC4_RETURN_PREFIX + value))
    assert result == int.from_bytes(value)
