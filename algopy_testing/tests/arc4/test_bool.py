import re

import algokit_utils
import algopy
import pytest
from algopy_testing import arc4
from algopy_testing.constants import ARC4_RETURN_PREFIX

from tests.common import AVMInvoker


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
    ],
)
def test_bool_bytes(get_avm_result: AVMInvoker, value: int) -> None:
    avm_result = get_avm_result("verify_bool_bytes", a=value)
    assert avm_result == arc4.Bool(bool(value)).bytes


@pytest.mark.parametrize(
    "value",
    [
        b"\x00",
        b"\x80",
    ],
)
def test_bool_from_bytes(get_avm_result: AVMInvoker, value: bytes) -> None:
    avm_result = get_avm_result("verify_bool_from_bytes", a=value)
    assert avm_result == arc4.Bool.from_bytes(value).native


@pytest.mark.parametrize(
    "value",
    [
        b"\x00",
        b"\x80",
    ],
)
def test_bool_from_log(get_avm_result: AVMInvoker, value: bytes) -> None:
    value = ARC4_RETURN_PREFIX + value
    avm_result = get_avm_result("verify_bool_from_log", a=value)
    assert avm_result == arc4.Bool.from_log(algopy.Bytes(value)).native


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        (b"\x00", b""),
        (b"\x80", b"\xff\x00\x01\x02"),
        (b"\x00", ARC4_RETURN_PREFIX[:3]),
    ],
)
def test_string_from_log_invalid_prefix(
    get_avm_result: AVMInvoker, value: bytes, prefix: bytes
) -> None:
    with pytest.raises(
        algokit_utils.LogicError,
        match=re.compile("(assert failed)|(extraction start \\d+ is beyond length)"),
    ):
        get_avm_result("verify_bool_from_log", a=prefix + value)
    with pytest.raises(ValueError, match="ABI return prefix not found"):
        arc4.Bool.from_log(algopy.Bytes(prefix + value))
