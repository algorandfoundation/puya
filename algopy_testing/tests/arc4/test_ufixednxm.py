import typing

import algokit_utils
import pytest
from algopy_testing import arc4
from algopy_testing.constants import ARC4_RETURN_PREFIX
from algopy_testing.primitives.bytes import Bytes

from tests.common import AVMInvoker
from tests.util import int_to_bytes


def _invalid_bytes_length_error(length: int) -> str:
    return f"value string must be in bytes and correspond to a ufixed{length}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", False),
        ("0.00000000", False),
        ("42.94967295", True),
    ],
)
def test_ufixednxm_bool(value: str, expected: bool) -> None:  # noqa: FBT001
    # just test the implementation as there is no AVM equivalent
    assert bool(arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]](value)) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "1",
        "25.5",
        "42.94967295",
    ],
)
def test_ufixednxm_bytes(get_avm_result: AVMInvoker, value: str) -> None:
    a = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]](value)
    avm_result = get_avm_result("verify_ufixednxm_bytes", a=int.from_bytes(a.bytes.value))
    assert avm_result == a.bytes


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "1",
        "25.5",
        "42.94967295",
        "11579208923731619542357098500868790785326998466564056403945758.4007913129639935",
    ],
)
def test_bigufixednxm_bytes(get_avm_result: AVMInvoker, value: str) -> None:
    a = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]](value)
    avm_result = get_avm_result("verify_bigufixednxm_bytes", a=int.from_bytes(a.bytes.value))
    assert avm_result == a.bytes


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
def test_ufixednxm_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    avm_result = get_avm_result("verify_ufixednxm_from_bytes", a=value)
    result = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_bytes(value)
    assert avm_result == int.from_bytes(result.bytes.value)


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 1),
        int_to_bytes(0, 8),
        int_to_bytes(255, 2),
        int_to_bytes(2**32 - 1, 8),
    ],
)
def test_ufixednxm_from_bytes_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(32)):
        get_avm_result("verify_ufixednxm_from_bytes", a=value)

    result = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_bytes(value)
    assert result.bytes == value


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 32),
        int_to_bytes(255, 32),
        int_to_bytes(2**256 - 1, 32),
        int_to_bytes(2**256 - 1),
    ],
)
def test_bigufixednxm_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    avm_result = get_avm_result("verify_bigufixednxm_from_bytes", a=value)
    result = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_bytes(value)
    assert avm_result == int.from_bytes(result.bytes.value)


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 16),
        int_to_bytes(0, 40),
        int_to_bytes(2**128 - 1, 16),
        int_to_bytes(2**256 - 1, 40),
    ],
)
def test_bigufixednxm_from_bytes_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(256)):
        get_avm_result("verify_bigufixednxm_from_bytes", a=value)

    result = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_bytes(value)
    assert result.bytes == value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (int_to_bytes(0, 4), 0),
        (int_to_bytes(255, 4), 255),
        (int_to_bytes(2**16, 4), 2**16),
        (int_to_bytes(2**32 - 1, 4), 2**32 - 1),
    ],
)
def test_ufixednxm_from_log(get_avm_result: AVMInvoker, value: bytes, expected: int) -> None:
    avm_result = get_avm_result("verify_ufixednxm_from_log", a=ARC4_RETURN_PREFIX + value)
    result = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_log(
        Bytes(ARC4_RETURN_PREFIX + value)
    )
    assert avm_result == expected
    assert avm_result == int.from_bytes(result.bytes.value)


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (int_to_bytes(255, 4), b""),
        (int_to_bytes(255, 4), b"\xff\x00\x01\x02"),
    ],
)
def test_ufixednxm_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    with pytest.raises(algokit_utils.LogicError, match="assert failed"):
        get_avm_result("verify_ufixednxm_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_log(Bytes(prefix + value))


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 1),
        int_to_bytes(0, 8),
        int_to_bytes(255, 2),
        int_to_bytes(2**32 - 1, 8),
    ],
)
def test_ufixednxm_from_log_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(32)):
        get_avm_result("verify_ufixednxm_from_log", a=ARC4_RETURN_PREFIX + value)

    result = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]].from_log(
        Bytes(ARC4_RETURN_PREFIX + value)
    )
    assert result.bytes == value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (int_to_bytes(0, 32), 0),
        (int_to_bytes(255, 32), 255),
        (int_to_bytes(2**16, 32), 2**16),
        (int_to_bytes(2**256 - 1, 32), 2**256 - 1),
    ],
)
def test_bigufixednxm_from_log(get_avm_result: AVMInvoker, value: bytes, expected: int) -> None:
    avm_result = get_avm_result("verify_bigufixednxm_from_log", a=ARC4_RETURN_PREFIX + value)
    result = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_log(
        Bytes(ARC4_RETURN_PREFIX + value)
    )
    assert avm_result == expected
    assert avm_result == int.from_bytes(result.bytes.value)


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (int_to_bytes(255, 32), b""),
        (int_to_bytes(255, 32), b"\xff\x00\x01\x02"),
    ],
)
def test_bigufixednxm_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    with pytest.raises(algokit_utils.LogicError, match="assert failed"):
        get_avm_result("verify_bigufixednxm_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_log(Bytes(prefix + value))


@pytest.mark.parametrize(
    "value",
    [
        int_to_bytes(0, 16),
        int_to_bytes(0, 40),
        int_to_bytes(2**128 - 1, 16),
        int_to_bytes(2**256 - 1, 40),
    ],
)
def test_bigufixednxm_from_log_invalid_length(get_avm_result: AVMInvoker, value: bytes) -> None:
    with pytest.raises(ValueError, match=_invalid_bytes_length_error(256)):
        get_avm_result("verify_bigufixednxm_from_log", a=ARC4_RETURN_PREFIX + value)

    result = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]].from_log(
        Bytes(ARC4_RETURN_PREFIX + value)
    )
    assert result.bytes == value
