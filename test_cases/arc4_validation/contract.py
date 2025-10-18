import typing

import algopy
from algopy import (
    ARC4Contract,
    Bytes,
    arc4,
)


class ARC4StaticStruct(arc4.Struct):
    foo: arc4.UInt64
    bar: arc4.UInt8


class ARC4DynamicStruct(arc4.Struct):
    foo: arc4.UInt64
    bar: arc4.UInt8
    baz: arc4.String


ARC4StaticTuple = arc4.Tuple[arc4.UInt64, arc4.UInt8]
ARC4DynamicTuple = arc4.Tuple[arc4.UInt64, arc4.UInt8, arc4.String]


class ValidationContract(ARC4Contract, state_totals=algopy.StateTotals(global_bytes=1)):
    @arc4.abimethod(validate_encoding=False)
    def validate_uint64(self, value: Bytes) -> None:
        arc4.UInt64.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_uint8(self, value: Bytes) -> None:
        arc4.UInt8.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_uint512(self, value: Bytes) -> None:
        arc4.UInt512.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_ufixed64(self, value: Bytes) -> None:
        arc4.UFixedNxM[typing.Literal[64], typing.Literal[2]].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_uint8_arr(self, value: Bytes) -> None:
        arc4.DynamicArray[arc4.UInt8].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_uint8_arr3(self, value: Bytes) -> None:
        arc4.StaticArray[arc4.UInt8, typing.Literal[3]].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_bool(self, value: Bytes) -> None:
        arc4.Bool.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_byte(self, value: Bytes) -> None:
        arc4.Byte.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_string(self, value: Bytes) -> None:
        arc4.String.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_bytes(self, value: Bytes) -> None:
        arc4.DynamicBytes.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_address(self, value: Bytes) -> None:
        arc4.Address.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_bool_arr(self, value: Bytes) -> None:
        arc4.DynamicArray[arc4.Bool].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_bool_arr3(self, value: Bytes) -> None:
        arc4.StaticArray[arc4.Bool, typing.Literal[3]].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_static_tuple(self, value: Bytes) -> None:
        ARC4StaticTuple.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_dynamic_tuple(self, value: Bytes) -> None:
        ARC4DynamicTuple.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_static_struct(self, value: Bytes) -> None:
        ARC4StaticStruct.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_dynamic_struct(self, value: Bytes) -> None:
        ARC4DynamicStruct.from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_static_struct_arr(self, value: Bytes) -> None:
        arc4.DynamicArray[ARC4StaticStruct].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_static_struct_arr3(self, value: Bytes) -> None:
        arc4.StaticArray[ARC4StaticStruct, typing.Literal[3]].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_dynamic_struct_arr(self, value: Bytes) -> None:
        arc4.DynamicArray[ARC4DynamicStruct].from_bytes(value).validate()

    @arc4.abimethod(validate_encoding=False)
    def validate_dynamic_struct_arr3(self, value: Bytes) -> None:
        arc4.StaticArray[ARC4DynamicStruct, typing.Literal[3]].from_bytes(value).validate()
