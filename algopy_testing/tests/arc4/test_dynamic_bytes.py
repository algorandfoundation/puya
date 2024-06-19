import copy
import typing

import algosdk
import pytest
from algopy_testing import Bytes, arc4

from tests.util import int_to_bytes

_abi_dynamic_bytes_type = algosdk.abi.ABIType.from_string("byte[]")
_abi_int_array_values = [0, 1, 8, 16, 32, 64, 128, 255, 20, 30, 40, 50, 111]
_abi_bytes_value = b"".join([int_to_bytes(value) for value in _abi_int_array_values])

_arc4_int_array_values = _abi_int_array_values
_arc4_int_bytes: arc4.DynamicBytes = arc4.DynamicBytes(*_arc4_int_array_values)

_arc4_uint8_array_values = [arc4.UInt8(value) for value in _abi_int_array_values]
_arc4_uint8_bytes: arc4.DynamicBytes = arc4.DynamicBytes(*_arc4_uint8_array_values)

_arc4_bytes_array_values = [arc4.Byte(value) for value in _abi_int_array_values]
_arc4_bytes_bytes: arc4.DynamicBytes = arc4.DynamicBytes(*_arc4_bytes_array_values)

_arc4_native_bytes_value = b"".join([int_to_bytes(value) for value in _abi_int_array_values])
_arc4_native_bytes_bytes: arc4.DynamicBytes = arc4.DynamicBytes(_arc4_native_bytes_value)

_arc4_algopy_bytes_value = Bytes(
    b"".join([int_to_bytes(value) for value in _abi_int_array_values])
)
_arc4_algopy_bytes_bytes: arc4.DynamicBytes = arc4.DynamicBytes(_arc4_algopy_bytes_value)


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_native_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_algopy_bytes_bytes,
        ),
    ],
)
def test_bytes(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi_result = _abi_dynamic_bytes_type.encode(abi_values)

    arc4_result = arc4_value.bytes

    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_native_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_algopy_bytes_bytes,
        ),
    ],
)
def test_copy(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi_result = _abi_dynamic_bytes_type.encode(abi_values)

    copy = arc4_value.copy()

    arc4_result = copy.bytes

    assert copy.length == arc4_value.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_native_bytes_bytes,
        ),
        (
            _abi_bytes_value,
            _arc4_algopy_bytes_bytes,
        ),
    ],
)
def test_get_item(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    i = 0
    while i < arc4_value.length:
        if hasattr(arc4_value[i], "native"):
            assert arc4_value[i].native == abi_values[i]
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_values", "arc4_values"),
    [
        (
            _abi_int_array_values,
            _arc4_bytes_array_values,
        ),
    ],
)
def test_append_to_empty(
    abi_values: list[typing.Any],
    arc4_values: list[typing.Any],
) -> None:
    arc4_empty_array = arc4.DynamicBytes()
    for value in arc4_values:
        arc4_empty_array.append(value)
    assert arc4_empty_array.length == len(arc4_values)

    abi_result = _abi_dynamic_bytes_type.encode(abi_values)
    assert arc4_empty_array.bytes == abi_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
    ],
)
def test_append(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi = copy.deepcopy(abi_values)
    abi.append(abi_values[0])
    abi.append(abi_values[-1])
    abi_result = _abi_dynamic_bytes_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4.append(arc4_value[0])
    arc4.append(arc4_value[-1])
    arc4_result = arc4.bytes

    assert arc4.length == arc4_value.length + 2
    assert len(abi) == arc4.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_values"),
    [
        (
            _abi_int_array_values,
            _arc4_bytes_array_values,
        ),
    ],
)
def test_extend_to_empty(
    abi_values: list[typing.Any],
    arc4_values: list[typing.Any],
) -> None:
    arc4_empty_array = arc4.DynamicBytes()
    extended_array = arc4_empty_array.copy()

    for value in arc4_values:
        arc4_empty_array.append(value)

    extended_array.extend(arc4_values)
    assert arc4_empty_array.length == extended_array.length

    abi_result = _abi_dynamic_bytes_type.encode(abi_values)
    assert extended_array.bytes == abi_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
    ],
)
def test_extend(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi = copy.deepcopy(abi_values)
    abi.extend([abi_values[0], abi_values[-1]])
    abi_result = _abi_dynamic_bytes_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4.extend([arc4_value[0], arc4_value[-1]])
    arc4_result = arc4.bytes

    assert arc4.length == arc4_value.length + 2
    assert len(abi) == arc4.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    "abi_values",
    [
        _abi_int_array_values,
        _abi_bytes_value,
    ],
)
def test_from_bytes(
    abi_values: list[typing.Any],
) -> None:
    i = 0
    arc4_value = arc4.DynamicBytes.from_bytes(_abi_dynamic_bytes_type.encode(abi_values))
    while i < arc4_value.length:
        if hasattr(arc4_value[i], "native"):
            assert arc4_value[i].native == abi_values[i]
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
    ],
)
def test_set_item(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi = copy.deepcopy(abi_values)
    temp = abi[-1]
    abi[-1] = abi[0]
    abi[0] = temp
    abi_result = _abi_dynamic_bytes_type.encode(abi)

    arc4 = arc4_value.copy()
    temp = arc4[-1]
    arc4[-1] = arc4[0]
    arc4[0] = temp
    arc4_result = arc4.bytes

    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
    ],
)
def test_pop(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi = copy.deepcopy(abi_values)
    abi_value_1 = abi.pop()
    abi_value_2 = abi.pop()
    abi_result = _abi_dynamic_bytes_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4_value_1 = arc4.pop()
    arc4_value_2 = arc4.pop()
    arc4_result = arc4.bytes

    assert arc4_value_1.native == abi_value_1
    assert arc4_value_2.native == abi_value_2
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_int_array_values,
            _arc4_int_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_uint8_bytes,
        ),
        (
            _abi_int_array_values,
            _arc4_bytes_bytes,
        ),
    ],
)
def test_add(
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicBytes,
) -> None:
    abi = copy.deepcopy(abi_values)
    abi = abi + abi
    abi_result = _abi_dynamic_bytes_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4_array = arc4 + arc4
    arc4_result = arc4_array.bytes

    assert arc4_array.length == arc4_value.length * 2
    assert len(abi) == arc4_array.length
    assert abi_result == arc4_result
