import copy
import typing

import pytest
from algopy_testing import arc4
from algosdk import abi

from tests.util import int_to_bytes

_abi_bool_array_type = abi.ABIType.from_string("bool[]")
_abi_bool_array_values = [True, True, False, True, False, True, True, False, True, False]
_arc4_bool_array_values = [arc4.Bool(value) for value in _abi_bool_array_values]
_arc4_bool_array: arc4.DynamicArray[arc4.Bool] = arc4.DynamicArray(*_arc4_bool_array_values)

_abi_uint256_array_type = abi.ABIType.from_string("uint256[]")
_abi_uint256_array_values = [0, 1, 2, 3, 2**8, 2**16, 2**32, 2**64, 2**128, 2**256 - 1]
_arc4_uint256_array_values = [arc4.UInt256(value) for value in _abi_uint256_array_values]
_arc4_uint256_array = arc4.DynamicArray[arc4.UInt256](*_arc4_uint256_array_values)

_abi_bool_array_of_array_type = abi.ABIType.from_string("bool[][]")
_abi_bool_array_of_array_values = [
    _abi_bool_array_values,
    _abi_bool_array_values,
]
_arc4_bool_array_of_array_values = [
    arc4.DynamicArray[arc4.Bool](*[arc4.Bool(value) for value in _abi_bool_array_values]),
    arc4.DynamicArray[arc4.Bool](*[arc4.Bool(value) for value in _abi_bool_array_values]),
]
_arc4_bool_array_of_array = arc4.DynamicArray[arc4.DynamicArray[arc4.Bool]](
    *_arc4_bool_array_of_array_values
)

_abi_uint256_array_of_array_type = abi.ABIType.from_string("uint256[][]")
_abi_uint256_array_of_array_values = [
    _abi_uint256_array_values,
    _abi_uint256_array_values,
]
_arc4_uint256_array_of_array_values = [
    arc4.DynamicArray[arc4.UInt256](*[arc4.UInt256(value) for value in _abi_uint256_array_values]),
    arc4.DynamicArray[arc4.UInt256](*[arc4.UInt256(value) for value in _abi_uint256_array_values]),
]
_arc4_uint256_array_of_array = arc4.DynamicArray[arc4.DynamicArray[arc4.UInt256]](
    *_arc4_uint256_array_of_array_values
)

_abi_uint256_array_of_static_array_type = abi.ABIType.from_string("uint256[10][]")
_abi_uint256_array_of_static_array_values = _abi_uint256_array_of_array_values
_arc4_uint256_array_of_static_array_values = [
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]](
        *[arc4.UInt256(value) for value in _abi_uint256_array_values]
    ),
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]](
        *[arc4.UInt256(value) for value in _abi_uint256_array_values]
    ),
]
_arc4_uint256_array_of_static_array = arc4.DynamicArray[
    arc4.StaticArray[arc4.UInt256, typing.Literal[10]]
](*_arc4_uint256_array_of_static_array_values)


_abi_string_array_type = abi.ABIType.from_string("string[]")
_abi_string_array_values = [
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
_arc4_string_array_values = [arc4.String(value) for value in _abi_string_array_values]
_arc4_string_array: arc4.DynamicArray[arc4.String] = arc4.DynamicArray(*_arc4_string_array_values)

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
_abi_bigufixednxm_array_type = abi.ABIType.from_string("ufixed256x16[]")
_abi_bigufixednxm_array_values = [int.from_bytes(x.bytes.value) for x in _bigufixednxm_values]
_arc4_bigufixednxm_array_values = _bigufixednxm_values
_arc4_bigufixednxm_array = arc4.DynamicArray[
    arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]
](*_arc4_bigufixednxm_array_values)

_abi_string_array_of_array_type = abi.ABIType.from_string("string[][]")
_abi_string_array_of_array_values = [
    _abi_string_array_values,
    _abi_string_array_values,
]
_arc4_string_array_of_array_values = [
    arc4.DynamicArray[arc4.String](*[arc4.String(value) for value in _abi_string_array_values]),
    arc4.DynamicArray[arc4.String](*[arc4.String(value) for value in _abi_string_array_values]),
]
_arc4_string_array_of_array = arc4.DynamicArray[arc4.DynamicArray[arc4.String]](
    *_arc4_string_array_of_array_values
)

_abi_string_array_of_array_of_array_type = abi.ABIType.from_string("string[][][]")
_abi_string_array_of_array_of_array_values = [
    [
        _abi_string_array_values,
        _abi_string_array_values,
        _abi_string_array_values,
    ],
    [
        _abi_string_array_values,
        _abi_string_array_values,
        _abi_string_array_values,
    ],
]
_arc4_string_array_of_array_of_array_values = [
    arc4.DynamicArray[arc4.DynamicArray[arc4.String]](
        *[
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
        ]
    ),
    arc4.DynamicArray[arc4.DynamicArray[arc4.String]](
        *[
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
            arc4.DynamicArray[arc4.String](
                *[arc4.String(value) for value in _abi_string_array_values]
            ),
        ]
    ),
]
_arc4_string_array_of_array_of_array = arc4.DynamicArray[
    arc4.DynamicArray[arc4.DynamicArray[arc4.String]]
](*_arc4_string_array_of_array_of_array_values)

_abi_tuple_array_type = abi.ABIType.from_string(
    "(string[],(string[],string,uint256),bool,uint256[3])[]"
)
_abi_tuple_array_values = [
    (
        _abi_string_array_values[:2],
        (
            _abi_string_array_values[6:8],
            _abi_string_array_values[9],
            _abi_uint256_array_values[4],
        ),
        _abi_bool_array_values[3],
        _abi_uint256_array_values[4:7],
    ),
] * 2
_arc4_tuple_array_values: list[
    arc4.Tuple[
        arc4.DynamicArray[arc4.String],
        arc4.Tuple[
            arc4.DynamicArray[arc4.String],
            arc4.String,
            arc4.UInt256,
        ],
        arc4.Bool,
        arc4.StaticArray[arc4.UInt256, typing.Literal[3]],
    ]
] = [
    arc4.Tuple(
        (
            arc4.DynamicArray(*_arc4_string_array_values[:2]),
            arc4.Tuple(
                (
                    arc4.DynamicArray(*_arc4_string_array_values[6:8]),
                    _arc4_string_array_values[9],
                    _arc4_uint256_array_values[4],
                )
            ),
            _arc4_bool_array_values[3],
            arc4.StaticArray(*_arc4_uint256_array_values[4:7]),
        )
    )
] * 2

_arc4_tuple_array: arc4.DynamicArray[
    arc4.Tuple[
        arc4.DynamicArray[arc4.String],
        arc4.Tuple[
            arc4.DynamicArray[arc4.String],
            arc4.String,
            arc4.UInt256,
        ],
        arc4.Bool,
        arc4.StaticArray[arc4.UInt256, typing.Literal[3]],
    ]
] = arc4.DynamicArray(*_arc4_tuple_array_values)


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            _abi_bool_array_type,
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_bytes(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
) -> None:
    abi_result = abi_type.encode(abi_values)

    arc4_result = arc4_value.bytes

    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            _abi_bool_array_type,
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_copy(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
) -> None:
    abi_result = abi_type.encode(abi_values)

    copy = arc4_value.copy()

    arc4_result = copy.bytes

    assert copy.length == arc4_value.length
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_values", "arc4_value"),
    [
        (
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_get_item(abi_values: list[typing.Any], arc4_value: arc4.DynamicArray) -> None:  # type: ignore[type-arg]
    i = 0
    while i < arc4_value.length:
        _compare_abi_and_arc4_values(arc4_value[i], abi_values[i])
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_empty_array", "arc4_values"),
    [
        (
            _abi_bool_array_type,
            _abi_bool_array_values,
            arc4.DynamicArray[arc4.Bool](),
            _arc4_bool_array_values,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            arc4.DynamicArray[arc4.UInt256](),
            _arc4_uint256_array_values,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            arc4.DynamicArray[arc4.String](),
            _arc4_string_array_values,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            arc4.DynamicArray[arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]](),
            _arc4_bigufixednxm_array_values,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.Bool]](),
            _arc4_bool_array_of_array_values,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.UInt256]](),
            _arc4_uint256_array_of_array_values,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            arc4.DynamicArray[arc4.StaticArray[arc4.UInt256, typing.Literal[10]]](),
            _arc4_uint256_array_of_static_array_values,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.String]](),
            _arc4_string_array_of_array_values,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.DynamicArray[arc4.String]]](),
            _arc4_string_array_of_array_of_array_values,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            arc4.DynamicArray[arc4.Tuple](),  # type: ignore[type-arg]
            _arc4_tuple_array_values,
        ),
    ],
)
def test_append_to_empty(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_empty_array: arc4.DynamicArray,  # type: ignore[type-arg]
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
            abi.ABIType.from_string("bool[]"),
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            abi.ABIType.from_string("uint256[]"),
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            abi.ABIType.from_string("string[]"),
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            abi.ABIType.from_string("ufixed256x16[]"),
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            abi.ABIType.from_string("bool[][]"),
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[][]"),
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[10][]"),
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            abi.ABIType.from_string("string[][]"),
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[][][]"),
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            abi.ABIType.from_string("(string[],(string[],string,uint256),bool,uint256[3])[]"),
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_append(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
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
            _abi_bool_array_type,
            _abi_bool_array_values,
            arc4.DynamicArray[arc4.Bool](),
            _arc4_bool_array_values,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            arc4.DynamicArray[arc4.UInt256](),
            _arc4_uint256_array_values,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            arc4.DynamicArray[arc4.String](),
            _arc4_string_array_values,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            arc4.DynamicArray[arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]](),
            _arc4_bigufixednxm_array_values,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.Bool]](),
            _arc4_bool_array_of_array_values,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.UInt256]](),
            _arc4_uint256_array_of_array_values,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            arc4.DynamicArray[arc4.StaticArray[arc4.UInt256, typing.Literal[10]]](),
            _arc4_uint256_array_of_static_array_values,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.String]](),
            _arc4_string_array_of_array_values,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.DynamicArray[arc4.String]]](),
            _arc4_string_array_of_array_of_array_values,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            arc4.DynamicArray[arc4.Tuple](),  # type: ignore[type-arg]
            _arc4_tuple_array_values,
        ),
    ],
)
def test_extend_to_empty(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_empty_array: arc4.DynamicArray,  # type: ignore[type-arg]
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
            abi.ABIType.from_string("bool[]"),
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            abi.ABIType.from_string("uint256[]"),
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            abi.ABIType.from_string("string[]"),
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            abi.ABIType.from_string("ufixed256x16[]"),
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            abi.ABIType.from_string("bool[][]"),
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[][]"),
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[10][]"),
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            abi.ABIType.from_string("string[][]"),
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[][][]"),
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            abi.ABIType.from_string("(string[],(string[],string,uint256),bool,uint256[3])[]"),
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_extend(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
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
            _abi_bool_array_type,
            _abi_bool_array_values,
            arc4.DynamicArray[arc4.Bool],
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            arc4.DynamicArray[arc4.UInt256],
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            arc4.DynamicArray[arc4.String],
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            arc4.DynamicArray[arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]],
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.Bool]],
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.UInt256]],
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            arc4.DynamicArray[arc4.StaticArray[arc4.UInt256, typing.Literal[10]]],
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.String]],
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            arc4.DynamicArray[arc4.DynamicArray[arc4.DynamicArray[arc4.String]]],
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            arc4.DynamicArray[
                arc4.Tuple[
                    arc4.DynamicArray[arc4.String],
                    arc4.Tuple[
                        arc4.DynamicArray[arc4.String],
                        arc4.String,
                        arc4.UInt256,
                    ],
                    arc4.Bool,
                    arc4.StaticArray[arc4.UInt256, typing.Literal[3]],
                ]
            ],
        ),
    ],
)
def test_from_bytes(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_type: type[arc4.DynamicArray],  # type: ignore[type-arg]
) -> None:
    i = 0
    arc4_value = arc4_type.from_bytes(abi_type.encode(abi_values))
    while i < arc4_value.length:
        _compare_abi_and_arc4_values(arc4_value[i], abi_values[i])
        i += 1

    assert len(abi_values) == arc4_value.length


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            _abi_bool_array_type,
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_set_item(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
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


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            _abi_bool_array_type,
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            _abi_uint256_array_type,
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            _abi_string_array_type,
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            _abi_bigufixednxm_array_type,
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            _abi_bool_array_of_array_type,
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            _abi_uint256_array_of_array_type,
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            _abi_uint256_array_of_static_array_type,
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            _abi_string_array_of_array_type,
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            _abi_string_array_of_array_of_array_type,
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            _abi_tuple_array_type,
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_pop(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
) -> None:
    abi = copy.deepcopy(abi_values)
    abi_value_1 = abi.pop()
    abi_value_2 = abi.pop()
    abi_result = abi_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4_value_1 = arc4.pop()
    arc4_value_2 = arc4.pop()
    arc4_result = arc4.bytes

    _compare_abi_and_arc4_values(arc4_value_1, abi_value_1)
    _compare_abi_and_arc4_values(arc4_value_2, abi_value_2)
    assert abi_result == arc4_result


@pytest.mark.parametrize(
    ("abi_type", "abi_values", "arc4_value"),
    [
        (
            abi.ABIType.from_string("bool[]"),
            _abi_bool_array_values,
            _arc4_bool_array,
        ),
        (
            abi.ABIType.from_string("uint256[]"),
            _abi_uint256_array_values,
            _arc4_uint256_array,
        ),
        (
            abi.ABIType.from_string("string[]"),
            _abi_string_array_values,
            _arc4_string_array,
        ),
        (
            abi.ABIType.from_string("ufixed256x16[]"),
            _abi_bigufixednxm_array_values,
            _arc4_bigufixednxm_array,
        ),
        (
            abi.ABIType.from_string("bool[][]"),
            _abi_bool_array_of_array_values,
            _arc4_bool_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[][]"),
            _abi_uint256_array_of_array_values,
            _arc4_uint256_array_of_array,
        ),
        (
            abi.ABIType.from_string("uint256[10][]"),
            _abi_uint256_array_of_static_array_values,
            _arc4_uint256_array_of_static_array,
        ),
        (
            abi.ABIType.from_string("string[][]"),
            _abi_string_array_of_array_values,
            _arc4_string_array_of_array,
        ),
        (
            abi.ABIType.from_string("string[][][]"),
            _abi_string_array_of_array_of_array_values,
            _arc4_string_array_of_array_of_array,
        ),
        (
            abi.ABIType.from_string("(string[],(string[],string,uint256),bool,uint256[3])[]"),
            _abi_tuple_array_values,
            _arc4_tuple_array,
        ),
    ],
)
def test_add(
    abi_type: abi.ABIType,
    abi_values: list[typing.Any],
    arc4_value: arc4.DynamicArray,  # type: ignore[type-arg]
) -> None:
    abi = copy.deepcopy(abi_values)
    abi = abi + abi
    abi_result = abi_type.encode(abi)

    arc4 = arc4_value.copy()
    arc4 = arc4 + arc4
    arc4_result = arc4.bytes

    assert arc4.length == arc4_value.length * 2
    assert len(abi) == arc4.length
    assert abi_result == arc4_result


def _compare_abi_and_arc4_values(
    arc4_value: typing.Any,
    abi_value: typing.Any,
) -> None:
    if hasattr(arc4_value, "_list") or isinstance(arc4_value, tuple):
        x = list(arc4_value) if isinstance(arc4_value, tuple) else arc4_value._list()
        j = 0
        while j < len(x):
            _compare_abi_and_arc4_values(x[j], abi_value[j])
            j += 1
    elif hasattr(arc4_value, "native"):
        assert arc4_value.native == abi_value
    else:
        assert arc4_value.bytes == int_to_bytes(abi_value, len(arc4_value.bytes))
