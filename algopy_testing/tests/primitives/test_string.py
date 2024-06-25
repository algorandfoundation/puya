import pytest
from algopy import String
from algopy_testing.constants import MAX_LOG_SIZE

from tests.common import AVMInvoker


@pytest.mark.parametrize(
    ("value"),
    [
        "",
        "hello",
        str("0" * (MAX_LOG_SIZE - 13)),  # Max log size is 1024
    ],
)
def test_string_init(value: str, get_avm_result: AVMInvoker) -> None:
    avm_result = get_avm_result("verify_string_init", a=value)
    assert avm_result == String(f"Hello, {value}")


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("hello", "he", True),
        ("hello", "lo", False),
    ],
)
def test_string_startswith(*, a: str, b: str, expected: bool, get_avm_result: AVMInvoker) -> None:
    avm_result = get_avm_result("verify_string_startswith", a=a, b=b)
    assert avm_result == expected
    assert String(a).startswith(String(b)) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("hello", "he", False),
        ("hello", "lo", True),
    ],
)
def test_string_endswith(*, a: str, b: str, expected: bool, get_avm_result: AVMInvoker) -> None:
    avm_result = get_avm_result("verify_string_endswith", a=a, b=b)
    assert avm_result == expected
    assert String(a).endswith(String(b)) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("hello", "world", "hello, world"),
        ("foo", "bar", "foo, bar"),
    ],
)
def test_string_join(*, a: str, b: str, expected: str, get_avm_result: AVMInvoker) -> None:
    avm_result = get_avm_result("verify_string_join", a=a, b=b)
    assert avm_result == expected
    assert String(", ").join((String(a), String(b))) == String(expected)


def test_string_bytes() -> None:
    assert String("hello").bytes == b"hello"
    assert String("").bytes == b""


def test_string_contains() -> None:
    assert "ell" in String("hello")
    assert "world" not in String("hello")
