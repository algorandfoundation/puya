import re

import algokit_utils
import algopy
import pytest
from algopy_testing import arc4
from algopy_testing.constants import ARC4_RETURN_PREFIX, MAX_LOG_SIZE

from tests.common import AVMInvoker
from tests.util import int_to_bytes


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0",
        "False",
    ],
)
def test_string_bool(value: str) -> None:
    assert bool(arc4.String(value)) == bool(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "hello",
        str("0" * (MAX_LOG_SIZE - 13)),  # Max log size is 1024
    ],
)
def test_string_init(get_avm_result: AVMInvoker, value: str) -> None:
    avm_result = get_avm_result("verify_string_init", a=value)
    assert avm_result == arc4.String(f"Hello, {value}")


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("hello", "world", "helloworld"),
        ("foo", "bar", "foobar"),
    ],
)
def test_string_add(get_avm_result: AVMInvoker, a: str, b: str, expected: str) -> None:
    avm_result = get_avm_result("verify_string_add", a=a, b=b)
    assert avm_result == expected
    assert arc4.String(a) + arc4.String(b) == expected


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("", ""),
        ("hello", "hello"),
        ("foo", "Foo"),
        ("foo", "bar"),
    ],
)
def test_string_eq(get_avm_result: AVMInvoker, a: str, b: str) -> None:
    avm_result = get_avm_result("verify_string_eq", a=a, b=b)
    result = arc4.String(a) == arc4.String(b)
    assert avm_result == result


@pytest.mark.parametrize(
    "value",
    [
        "",
        "hello",
        str("0" * (MAX_LOG_SIZE - 13)),  # Max log size is 1024
    ],
)
def test_string_bytes(get_avm_result: AVMInvoker, value: str) -> None:
    avm_result = get_avm_result("verify_string_bytes", a=value)
    assert avm_result == arc4.String(value).bytes


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"hello",
        str("0" * (MAX_LOG_SIZE - 13)).encode(),  # Max log size is 1024
    ],
)
def test_string_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    value = int_to_bytes(len(value), 2) + value
    avm_result = get_avm_result("verify_string_from_bytes", a=value)
    result = arc4.String.from_bytes(value)
    assert avm_result == result


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"hello",
        str("0" * (MAX_LOG_SIZE - 13)).encode(),  # Max log size is 1024
    ],
)
def test_string_from_log(get_avm_result: AVMInvoker, value: bytes) -> None:
    value = ARC4_RETURN_PREFIX + int_to_bytes(len(value), 2) + value
    avm_result = get_avm_result("verify_string_from_log", a=value)
    result = arc4.String.from_log(algopy.Bytes(value))
    assert avm_result == result


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (b"", b""),
        (b"hello", b"\xff\x00\x01\x02"),
        (str("0" * (MAX_LOG_SIZE - 13)).encode(), ARC4_RETURN_PREFIX[:3]),  # Max log size is 1024
    ],
)
def test_string_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    value = int_to_bytes(len(value), 2) + value
    with pytest.raises(
        algokit_utils.LogicError,
        match=re.compile("(assert failed)|(extraction start \\d+ is beyond length)"),
    ):
        get_avm_result("verify_string_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.UInt256.from_log(algopy.Bytes(prefix + value))
