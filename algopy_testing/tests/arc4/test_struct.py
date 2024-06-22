import typing

import pytest
from algopy_testing import arc4
from algosdk import abi

from tests.util import int_to_bytes

_abi_string = "hello"
_abi_uint64 = 42
_abi_bool = True


_arc4_string = arc4.String("hello")
_arc4_uint64 = arc4.UInt64(42)
_arc4_bool = arc4.Bool(True)  # noqa: FBT003


class Swapped(arc4.Struct):
    b: arc4.UInt64
    c: arc4.Bool
    d: arc4.String


class Swapped1(Swapped):
    a: arc4.Tuple[arc4.UInt64, arc4.Bool, arc4.Bool]


class Swapped2(Swapped):
    a: arc4.Tuple[
        arc4.Tuple[arc4.UInt64, arc4.Bool, arc4.Bool],
        arc4.Tuple[arc4.UInt64, arc4.Bool, arc4.Bool],
    ]


class Swapped3(Swapped):
    a: arc4.Tuple[
        arc4.DynamicArray[arc4.String],
        arc4.DynamicArray[arc4.String],
        arc4.String,
        arc4.UInt64,
        arc4.Bool,
        arc4.StaticArray[arc4.UInt64, typing.Literal[3]],
    ]


class Swapped4(Swapped):
    a: arc4.Tuple[
        arc4.Tuple[arc4.Bool, arc4.DynamicArray[arc4.String], arc4.String],
        arc4.UInt64,
        arc4.StaticArray[arc4.UInt64, typing.Literal[3]],
    ]


class Swapped5(Swapped):
    a: arc4.Tuple[
        arc4.Tuple[arc4.Bool, arc4.DynamicArray[arc4.String], arc4.String],
        arc4.Tuple[arc4.UInt64, arc4.StaticArray[arc4.UInt64, typing.Literal[3]]],
    ]


class Swapped6(Swapped):
    a: arc4.Tuple[
        arc4.Tuple[arc4.Bool, arc4.Tuple[arc4.DynamicArray[arc4.String], arc4.String]],
        arc4.Tuple[arc4.UInt64, arc4.StaticArray[arc4.UInt64, typing.Literal[3]]],
    ]


_test_data = [
    (
        abi.ABIType.from_string("(uint64,bool,string,(uint64,bool,bool))"),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                _abi_uint64,
                _abi_bool,
                _abi_bool,
            ),
        ),
        Swapped1(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    _arc4_uint64,
                    _arc4_bool,
                    _arc4_bool,
                )
            ),
        ),
    ),
    (
        abi.ABIType.from_string("(uint64,bool,string,((uint64,bool,bool),(uint64,bool,bool)))"),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                (
                    _abi_uint64,
                    _abi_bool,
                    _abi_bool,
                ),
                (
                    _abi_uint64,
                    _abi_bool,
                    _abi_bool,
                ),
            ),
        ),
        Swapped2(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    arc4.Tuple(
                        (
                            _arc4_uint64,
                            _arc4_bool,
                            _arc4_bool,
                        )
                    ),
                    arc4.Tuple(
                        (
                            _arc4_uint64,
                            _arc4_bool,
                            _arc4_bool,
                        )
                    ),
                )
            ),
        ),
        arc4.Tuple[
            arc4.Tuple[arc4.UInt64, arc4.Bool, arc4.Bool],
            arc4.Tuple[arc4.UInt64, arc4.Bool, arc4.Bool],
        ],
    ),
    (
        abi.ABIType.from_string(
            "(uint64,bool,string,(string[],string[],string,uint64,bool,uint64[3]))"
        ),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                [_abi_string, _abi_string],
                [_abi_string, _abi_string],
                _abi_string,
                _abi_uint64,
                _abi_bool,
                [_abi_uint64, _abi_uint64, _abi_uint64],
            ),
        ),
        Swapped3(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    arc4.DynamicArray(_arc4_string, _arc4_string),
                    arc4.DynamicArray(_arc4_string, _arc4_string),
                    _arc4_string,
                    _arc4_uint64,
                    _arc4_bool,
                    arc4.StaticArray(_arc4_uint64, _arc4_uint64, _arc4_uint64),
                ),
            ),
        ),
    ),
    (
        abi.ABIType.from_string("(uint64,bool,string,((bool,string[],string),uint64,uint64[3]))"),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                (
                    _abi_bool,
                    [_abi_string, _abi_string],
                    _abi_string,
                ),
                _abi_uint64,
                [_abi_uint64, _abi_uint64, _abi_uint64],
            ),
        ),
        Swapped4(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    arc4.Tuple(
                        (
                            _arc4_bool,
                            arc4.DynamicArray(_arc4_string, _arc4_string),
                            _arc4_string,
                        )
                    ),
                    _arc4_uint64,
                    arc4.StaticArray(_arc4_uint64, _arc4_uint64, _arc4_uint64),
                )
            ),
        ),
    ),
    (
        abi.ABIType.from_string(
            "(uint64,bool,string,((bool,string[],string),(uint64,uint64[3])))"
        ),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                (
                    _abi_bool,
                    [_abi_string, _abi_string],
                    _abi_string,
                ),
                (
                    _abi_uint64,
                    [_abi_uint64, _abi_uint64, _abi_uint64],
                ),
            ),
        ),
        Swapped5(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    arc4.Tuple(
                        (
                            _arc4_bool,
                            arc4.DynamicArray(_arc4_string, _arc4_string),
                            _arc4_string,
                        )
                    ),
                    arc4.Tuple(
                        (
                            _arc4_uint64,
                            arc4.StaticArray(_arc4_uint64, _arc4_uint64, _arc4_uint64),
                        )
                    ),
                )
            ),
        ),
    ),
    (
        abi.ABIType.from_string(
            "(uint64,bool,string,((bool,(string[],string)),(uint64,uint64[3])))"
        ),
        (
            _abi_uint64,
            _abi_bool,
            _abi_string,
            (
                (
                    _abi_bool,
                    (
                        [_abi_string, _abi_string],
                        _abi_string,
                    ),
                ),
                (
                    _abi_uint64,
                    [_abi_uint64, _abi_uint64, _abi_uint64],
                ),
            ),
        ),
        Swapped6(
            _arc4_uint64,
            _arc4_bool,
            _arc4_string,
            arc4.Tuple(
                (
                    arc4.Tuple(
                        (
                            _arc4_bool,
                            arc4.Tuple(
                                (
                                    arc4.DynamicArray(_arc4_string, _arc4_string),
                                    _arc4_string,
                                )
                            ),
                        )
                    ),
                    arc4.Tuple(
                        (
                            _arc4_uint64,
                            arc4.StaticArray(_arc4_uint64, _arc4_uint64, _arc4_uint64),
                        )
                    ),
                )
            ),
        ),
    ),
]


@pytest.mark.parametrize(
    ("abi_type", "abi_value", "arc4_value"),
    [(d[0], d[1], d[2]) for d in _test_data],
)
def test_bytes(abi_type: abi.ABIType, abi_value: tuple, arc4_value: Swapped) -> None:  # type: ignore[type-arg]
    abi_result = abi_type.encode(abi_value)
    assert arc4_value.bytes == abi_result


@pytest.mark.parametrize(
    ("abi_type", "abi_value", "arc4_type"),
    [(d[0], d[1], type(d[2])) for d in _test_data],
)
def test_from_bytes(abi_type: abi.ABIType, abi_value: tuple, arc4_type: type[Swapped]) -> None:  # type: ignore[type-arg]
    abi_bytes = abi_type.encode(abi_value)

    arc4_value = arc4_type.from_bytes(abi_bytes)
    arc4_result = arc4_value._value

    i = 0
    while i < len(arc4_result):
        _compare_abi_and_arc4_values(arc4_result[i], abi_value[i])
        i += 1

    assert len(abi_value) == len(arc4_result)


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
