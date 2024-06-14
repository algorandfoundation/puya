import copy
import typing

import pytest
from algopy_testing import arc4
from algosdk import abi

from tests.util import int_to_bytes

_abi_bool_static_array_type = abi.ABIType.from_string("bool[10]")
_abi_bool_static_array_values = [True, True, False, True, False, True, True, False, True, False]
_arc4_bool_static_array_values = [arc4.Bool(value) for value in _abi_bool_static_array_values]
_arc4_bool_static_array: arc4.StaticArray[arc4.Bool, typing.Literal[10]] = arc4.StaticArray(
    *_arc4_bool_static_array_values
)

_abi_uint256_static_array_type = abi.ABIType.from_string("uint256[10]")
_abi_uint256_static_array_values = [0, 1, 2, 3, 2**8, 2**16, 2**32, 2**64, 2**128, 2**256 - 1]
_arc4_uint256_static_array_values = [
    arc4.UInt256(value) for value in _abi_uint256_static_array_values
]
_arc4_uint256_static_array = arc4.StaticArray[arc4.UInt256, typing.Literal[10]](
    *_arc4_uint256_static_array_values
)


_abi_uint256_static_array_of_array_type = abi.ABIType.from_string("uint256[10][2]")
_abi_uint256_static_array_of_array_values = [
    _abi_uint256_static_array_values,
    _abi_uint256_static_array_values,
]
_arc4_uint256_static_array_of_array_values = [
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]](
        *[arc4.UInt256(value) for value in _abi_uint256_static_array_values]
    ),
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]](
        *[arc4.UInt256(value) for value in _abi_uint256_static_array_values]
    ),
]
_arc4_uint256_static_array_of_array = arc4.StaticArray[
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]], typing.Literal[2]
](*_arc4_uint256_static_array_of_array_values)


_abi_string_static_array_type = abi.ABIType.from_string("string[10]")
_abi_string_static_array_values = [
    "",
    "1",
    "hello",
    "World",
    str(2**8),
    str(2**16),
    str(2**32),
    str(2**64),
    str(2**128),
    str(2**256),
]
_arc4_string_static_array_values = [
    arc4.String(value) for value in _abi_string_static_array_values
]
_arc4_string_static_array: arc4.StaticArray[arc4.String, typing.Literal[10]] = arc4.StaticArray(
    *_arc4_string_static_array_values
)

_bigufixednxm_values = [
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("0"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("1"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("2"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("3"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("255"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("65536"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("4294967295"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("1844.6744073709551616"),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]](
        "340282366920938463463374.607431768211456"
    ),
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]](
        "11579208923731619542357098500868790785326998466564056403945758.4007913129639935"
    ),
]
_abi_bigufixednxm_static_array_type = abi.ABIType.from_string("ufixed256x16[10]")
_abi_bigufixednxm_static_array_values = [
    int.from_bytes(x.bytes.value) for x in _bigufixednxm_values
]
_arc4_bigufixednxm_static_array_values = _bigufixednxm_values
_arc4_bigufixednxm_static_array = arc4.StaticArray[
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]], typing.Literal[10]
](*_arc4_bigufixednxm_static_array_values)


_abi_string_static_array_of_array_type = abi.ABIType.from_string("string[10][2]")
_abi_string_static_array_of_array_values = [
    _abi_string_static_array_values,
    _abi_string_static_array_values,
]
_arc4_string_static_array_of_array_values = [
    arc4.StaticArray[arc4.String, typing.Literal[10]](
        *[arc4.String(value) for value in _abi_string_static_array_values]
    ),
    arc4.StaticArray[arc4.String, typing.Literal[10]](
        *[arc4.String(value) for value in _abi_string_static_array_values]
    ),
]
_arc4_string_static_array_of_array = arc4.StaticArray[
    arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[2]
](*_arc4_string_static_array_of_array_values)


_abi_string_static_array_of_array_of_array_type = abi.ABIType.from_string("string[10][3][2]")
_abi_string_static_array_of_array_of_array_values = [
    [
        _abi_string_static_array_values,
        _abi_string_static_array_values,
        _abi_string_static_array_values,
    ],
    [
        _abi_string_static_array_values,
        _abi_string_static_array_values,
        _abi_string_static_array_values,
    ],
]
_arc4_string_static_array_of_array_of_array_values = [
    arc4.StaticArray[arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]](
        *[
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
        ]
    ),
    arc4.StaticArray[arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]](
        *[
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
            arc4.StaticArray[arc4.String, typing.Literal[10]](
                *[arc4.String(value) for value in _abi_string_static_array_values]
            ),
        ]
    ),
]
_arc4_string_static_array_of_array_of_array = arc4.StaticArray[
    arc4.StaticArray[arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]],
    typing.Literal[2],
](*_arc4_string_static_array_of_array_of_array_values)


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (_abi_bool_static_array_type, _abi_bool_static_array_values, _arc4_bool_static_array),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_bytes(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.StaticArray,  # type: ignore[type-arg]
) -> None:
    abi_result = abi_type.encode(abi_values)

    arc4_result = arc4_value.bytes

    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (_abi_bool_static_array_type, _abi_bool_static_array_values, _arc4_bool_static_array),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_copy(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.StaticArray,  # type: ignore[type-arg]
) -> None:
    abi_result = abi_type.encode(abi_values)

    copy = arc4_value.copy()

    arc4_result = copy.bytes

    assert copy.length == arc4_value.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (_abi_bool_static_array_values, _arc4_bool_static_array),
        (
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_get_item(abi_values: list[typing.Any], arc4_value: arc4.StaticArray) -> None:  # type: ignore[type-arg]
    i = 0
    while i < arc4_value.length:
        if hasattr(arc4_value[i], "native"):
            assert arc4_value[i].native == abi_values[i]
        elif hasattr(arc4_value[i], "_list"):
            x = arc4_value[i]._list()  # noqa: SLF001
            j = 0
            while j < len(x):
                if hasattr(x[j], "_list"):
                    assert x[j]._list() == abi_values[i][j]  # noqa: SLF001
                else:
                    assert x[j] == abi_values[i][j]
                j += 1
        else:
            assert arc4_value[i].bytes == int_to_bytes(abi_values[i], len(arc4_value[i].bytes))
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_empty_array", "arc4_values"),
    [
        (
            _abi_bool_static_array_type,
            _abi_bool_static_array_values,
            arc4.StaticArray[arc4.Bool, typing.Literal[0]](),
            _arc4_bool_static_array_values,
        ),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            arc4.StaticArray[arc4.UInt256, typing.Literal[0]](),
            _arc4_uint256_static_array_values,
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            arc4.StaticArray[arc4.String, typing.Literal[0]](),
            _arc4_string_static_array_values,
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            arc4.StaticArray[
                arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]], typing.Literal[0]
            ](),
            _arc4_bigufixednxm_static_array_values,
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[arc4.UInt256, typing.Literal[10]], typing.Literal[0]
            ](),
            _arc4_uint256_static_array_of_array_values,
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[0]
            ](),
            _arc4_string_static_array_of_array_values,
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[
                    arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]
                ],
                typing.Literal[0],
            ](),
            _arc4_string_static_array_of_array_of_array_values,
        ),
    ],
)
def test_append_to_empty(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_empty_array: arc4.StaticArray,  # type: ignore[type-arg]
    arc4_values: list[typing.Any],
) -> None:
    for value in arc4_values:
        arc4_empty_array.append(value)
    assert arc4_empty_array.length == len(arc4_values)

    abi_result = abi_type.encode(abi_values)
    assert arc4_empty_array.bytes == abi_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            abi.ABIType.from_string("bool[12]"),
            _abi_bool_static_array_values,
            _arc4_bool_static_array,
        ),
        (
            abi.ABIType.from_string("uint256[12]"),
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            abi.ABIType.from_string("string[12]"),
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            abi.ABIType.from_string("ufixed256x16[12]"),
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            abi.ABIType.from_string("uint256[10][4]"),
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[10][4]"),
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[10][3][4]"),
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_append(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.StaticArray,  # type: ignore[type-arg]
) -> None:
    abi = copy.deepcopy(abi_values)
    abi.append(abi_values[0])
    abi.append(abi_values[-1])
    abi_result = abi_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4.append(arc4_value[0])
    arc4.append(arc4_value[-1])
    arc4_result = arc4.bytes

    assert arc4.length == arc4_value.length + 2
    assert len(abi) == arc4.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_empty_array", "arc4_values"),
    [
        (
            _abi_bool_static_array_type,
            _abi_bool_static_array_values,
            arc4.StaticArray[arc4.Bool, typing.Literal[0]](),
            _arc4_bool_static_array_values,
        ),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            arc4.StaticArray[arc4.UInt256, typing.Literal[0]](),
            _arc4_uint256_static_array_values,
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            arc4.StaticArray[arc4.String, typing.Literal[0]](),
            _arc4_string_static_array_values,
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            arc4.StaticArray[
                arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]], typing.Literal[0]
            ](),
            _arc4_bigufixednxm_static_array_values,
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[arc4.UInt256, typing.Literal[10]], typing.Literal[0]
            ](),
            _arc4_uint256_static_array_of_array_values,
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[0]
            ](),
            _arc4_string_static_array_of_array_values,
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[
                    arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]
                ],
                typing.Literal[0],
            ](),
            _arc4_string_static_array_of_array_of_array_values,
        ),
    ],
)
def test_extend_to_empty(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_empty_array: arc4.StaticArray,  # type: ignore[type-arg]
    arc4_values: list[typing.Any],
) -> None:
    extended_array = arc4_empty_array.copy()

    for value in arc4_values:
        arc4_empty_array.append(value)

    extended_array.extend(arc4_values)
    assert arc4_empty_array.length == extended_array.length

    abi_result = abi_type.encode(abi_values)
    assert extended_array.bytes == abi_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            abi.ABIType.from_string("bool[12]"),
            _abi_bool_static_array_values,
            _arc4_bool_static_array,
        ),
        (
            abi.ABIType.from_string("uint256[12]"),
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            abi.ABIType.from_string("string[12]"),
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            abi.ABIType.from_string("ufixed256x16[12]"),
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            abi.ABIType.from_string("uint256[10][4]"),
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[10][4]"),
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[10][3][4]"),
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_extend(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.StaticArray,  # type: ignore[type-arg]
) -> None:
    abi = copy.deepcopy(abi_values)
    abi.extend([abi_values[0], abi_values[-1]])
    abi_result = abi_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4.extend([arc4_value[0], arc4_value[-1]])
    arc4_result = arc4.bytes

    assert arc4.length == arc4_value.length + 2
    assert len(abi) == arc4.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_type"),
    [
        (
            _abi_bool_static_array_type,
            _abi_bool_static_array_values,
            arc4.StaticArray[arc4.Bool, typing.Literal[10]],
        ),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            arc4.StaticArray[arc4.UInt256, typing.Literal[10]],
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            arc4.StaticArray[arc4.String, typing.Literal[10]],
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            arc4.StaticArray[
                arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]], typing.Literal[10]
            ],
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[arc4.UInt256, typing.Literal[10]], typing.Literal[2]
            ],
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            arc4.StaticArray[arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[2]],
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            arc4.StaticArray[
                arc4.StaticArray[
                    arc4.StaticArray[arc4.String, typing.Literal[10]], typing.Literal[3]
                ],
                typing.Literal[2],
            ],
        ),
    ],
)
def test_from_bytes(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_type: type[arc4.StaticArray],  # type: ignore[type-arg]
) -> None:
    i = 0
    arc4_value = arc4_type.from_bytes(abi_type.encode(abi_values))
    while i < arc4_value.length:
        if hasattr(arc4_value[i], "native"):
            assert arc4_value[i].native == abi_values[i]
        elif hasattr(arc4_value[i], "_list"):
            x = arc4_value[i]._list()  # noqa: SLF001
            j = 0
            while j < len(x):
                if hasattr(x[j], "_list"):
                    assert x[j]._list() == abi_values[i][j]  # noqa: SLF001
                else:
                    assert x[j] == abi_values[i][j]
                j += 1
        else:
            assert arc4_value[i].bytes == int_to_bytes(abi_values[i], len(arc4_value[i].bytes))
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (_abi_bool_static_array_type, _abi_bool_static_array_values, _arc4_bool_static_array),
        (
            _abi_uint256_static_array_type,
            _abi_uint256_static_array_values,
            _arc4_uint256_static_array,
        ),
        (
            _abi_string_static_array_type,
            _abi_string_static_array_values,
            _arc4_string_static_array,
        ),
        (
            _abi_bigufixednxm_static_array_type,
            _abi_bigufixednxm_static_array_values,
            _arc4_bigufixednxm_static_array,
        ),
        (
            _abi_uint256_static_array_of_array_type,
            _abi_uint256_static_array_of_array_values,
            _arc4_uint256_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_type,
            _abi_string_static_array_of_array_values,
            _arc4_string_static_array_of_array,
        ),
        (
            _abi_string_static_array_of_array_of_array_type,
            _abi_string_static_array_of_array_of_array_values,
            _arc4_string_static_array_of_array_of_array,
        ),
    ],
)
def test_set_item(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.StaticArray,  # type: ignore[type-arg]
) -> None:
    abi = copy.deepcopy(abi_values)
    temp = abi[-1]
    abi[-1] = abi[0]
    abi[0] = temp
    abi_result = abi_type.encode(abi)

    arc4 = arc4_value.copy()
    temp = arc4[-1]
    arc4[-1] = arc4[0]
    arc4[0] = temp
    arc4_result = arc4.bytes

    assert abi_result == arc4_result
