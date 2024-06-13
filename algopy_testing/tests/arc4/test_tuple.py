import pytest
from algopy_testing import arc4
from algosdk import abi

_abi_string = "hello"
_abi_uint8 = 42
_abi_bool = True


_arc4_string = arc4.String("hello")
_arc4_uint8 = arc4.UInt8(42)
_arc4_bool = arc4.Bool(True)  # noqa: FBT003


@pytest.mark.parametrize(
    ("abi_type", "abi_value", "arc4_value"),
    [
        (
            abi.ABIType.from_string("(string,uint8,bool)"),
            (
                _abi_string,
                _abi_uint8,
                _abi_bool,
            ),
            arc4.Tuple(
                (
                    _arc4_string,
                    _arc4_uint8,
                    _arc4_bool,
                )
            ),
        ),
        (
            abi.ABIType.from_string("(string[],string[],string,uint8,bool,uint8[3])"),
            (
                [_abi_string, _abi_string],
                [_abi_string, _abi_string],
                _abi_string,
                _abi_uint8,
                _abi_bool,
                [_abi_uint8, _abi_uint8, _abi_uint8],
            ),
            arc4.Tuple(
                (
                    arc4.DynamicArray(*[_arc4_string, _arc4_string]),
                    arc4.DynamicArray(*[_arc4_string, _arc4_string]),
                    _arc4_string,
                    _arc4_uint8,
                    _arc4_bool,
                    arc4.StaticArray(*[_arc4_uint8, _arc4_uint8, _arc4_uint8]),
                ),
            ),
        ),
    ],
)
def test_bytes(abi_type: abi.ABIType, abi_value: tuple, arc4_value: arc4.Tuple) -> None:  # type: ignore[type-arg]
    abi_result = abi_type.encode(abi_value)
    arc4_result = arc4_value.bytes
    assert arc4_result == abi_result
