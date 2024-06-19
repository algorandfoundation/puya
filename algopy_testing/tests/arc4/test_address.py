import algopy_testing.primitives as algopy
import algosdk
import pytest
from algopy_testing import arc4
from algopy_testing.models import Account

_abi_address_type = algosdk.abi.ABIType.from_string("address")

_test_values = [
    b"\x00" * 32,
    b"\x01" * 32,
    b"\xff" * 32,
    b"\x00" * 31 + b"\xff",
]


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bytes_from_bytes(value: bytes) -> None:
    abi_result = _abi_address_type.encode(value)
    arc4_result = arc4.Address(algopy.Bytes(value)).bytes
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bytes_from_str(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    abi_result = _abi_address_type.encode(str_value)
    arc4_result = arc4.Address(str_value).bytes
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bytes_from_account(value: bytes) -> None:
    account = Account(algopy.Bytes(value))
    abi_result = _abi_address_type.encode(value)
    arc4_result = arc4.Address(account).bytes
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bool_from_bytes(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    arc4_result = bool(arc4.Address(algopy.Bytes(value)))
    assert arc4_result == (str_value != algosdk.constants.ZERO_ADDRESS)


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bool_from_str(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    arc4_result = bool(arc4.Address(str_value))
    assert arc4_result == (str_value != algosdk.constants.ZERO_ADDRESS)


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_bool_from_account(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    account = Account(algopy.Bytes(value))
    arc4_result = bool(arc4.Address(account))
    assert arc4_result == (str_value != algosdk.constants.ZERO_ADDRESS)


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_copy_from_bytes(value: bytes) -> None:
    abi_result = _abi_address_type.encode(value)
    arc4_value = arc4.Address(algopy.Bytes(value))
    copy = arc4_value.copy()
    assert copy.length == arc4_value.length
    assert abi_result == copy.bytes


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_copy_from_str(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    abi_result = _abi_address_type.encode(str_value)
    arc4_value = arc4.Address(str_value)
    copy = arc4_value.copy()
    assert copy.length == arc4_value.length
    assert abi_result == copy.bytes


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_copy_from_account(value: bytes) -> None:
    account = Account(algopy.Bytes(value))
    abi_result = _abi_address_type.encode(value)
    arc4_value = arc4.Address(account)
    copy = arc4_value.copy()
    assert copy.length == arc4_value.length
    assert abi_result == copy.bytes


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_get_item_from_bytes(value: bytes) -> None:
    input_bytes = algopy.Bytes(value)
    arc4_value = arc4.Address(algopy.Bytes(value))
    for idx, x in enumerate(arc4_value):
        assert x.bytes == input_bytes[idx].value
    assert input_bytes.length == arc4_value.length


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_get_item_from_str(value: bytes) -> None:
    input_bytes = algopy.Bytes(value)
    str_value = algosdk.encoding.encode_address(value)
    arc4_value = arc4.Address(str_value)
    for idx, x in enumerate(arc4_value):
        assert x.bytes == input_bytes[idx].value
    assert input_bytes.length == arc4_value.length


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_get_item_from_account(value: bytes) -> None:
    input_bytes = algopy.Bytes(value)
    account = Account(algopy.Bytes(value))
    arc4_value = arc4.Address(account)
    for idx, x in enumerate(arc4_value):
        assert x.bytes == input_bytes[idx].value
    assert input_bytes.length == arc4_value.length


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_comparison_with_self_from_bytes(value: bytes) -> None:
    arc4_value = arc4.Address(algopy.Bytes(value))
    str_value = algosdk.encoding.encode_address(value)
    assert arc4_value == str_value

    account = Account(algopy.Bytes(value))
    assert arc4_value == account

    assert arc4_value == arc4.Address(str_value)


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_comparison_with_self_from_str(value: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    arc4_value = arc4.Address(str_value)
    assert arc4_value == str_value

    account = Account(algopy.Bytes(value))
    assert arc4_value == account

    assert arc4_value == arc4.Address(account)


@pytest.mark.parametrize(
    "value",
    _test_values,
)
def test_comparison_with_self_from_account(value: bytes) -> None:
    account = Account(algopy.Bytes(value))
    arc4_value = arc4.Address(account)
    assert arc4_value == account

    str_value = algosdk.encoding.encode_address(value)
    assert arc4_value == str_value

    assert arc4_value == arc4.Address(algopy.Bytes(value))


@pytest.mark.parametrize(
    ("value", "other"),
    zip(_test_values, reversed(_test_values), strict=False),
)
def test_comparison_with_other_from_bytes(value: bytes, other: bytes) -> None:
    arc4_value = arc4.Address(algopy.Bytes(value))

    other_str_value = algosdk.encoding.encode_address(other)
    assert arc4_value != other_str_value

    other_account = Account(algopy.Bytes(other))
    assert arc4_value != other_account

    assert arc4_value != arc4.Address(other_str_value)


@pytest.mark.parametrize(
    ("value", "other"),
    zip(_test_values, reversed(_test_values), strict=False),
)
def test_comparison_with_other_from_str(value: bytes, other: bytes) -> None:
    str_value = algosdk.encoding.encode_address(value)
    arc4_value = arc4.Address(str_value)

    other_str_value = algosdk.encoding.encode_address(other)
    assert arc4_value != other_str_value

    other_account = Account(algopy.Bytes(other))
    assert arc4_value != other_account

    assert arc4_value != arc4.Address(other_account)


@pytest.mark.parametrize(
    ("value", "other"),
    zip(_test_values, reversed(_test_values), strict=False),
)
def test_comparison_with_other_from_account(value: bytes, other: bytes) -> None:
    account = Account(algopy.Bytes(value))
    arc4_value = arc4.Address(account)

    other_str_value = algosdk.encoding.encode_address(other)
    assert arc4_value != other_str_value

    other_account = Account(algopy.Bytes(other))
    assert arc4_value != other_account

    assert arc4_value != arc4.Address(algopy.Bytes(other))
