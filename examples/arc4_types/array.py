import typing as t

from algopy import Bytes, Contract, UInt64, uenumerate
from algopy.arc4 import (
    DynamicArray,
    StaticArray,
    String,
    UFixedNxM,
    UInt8,
    UInt16,
    UInt32,
)

AliasedDynamicArray: t.TypeAlias = DynamicArray[UInt16]
AliasedStaticArray: t.TypeAlias = StaticArray[UInt8, t.Literal[1]]

Decimal: t.TypeAlias = UFixedNxM[t.Literal[64], t.Literal[10]]


class Arc4ArraysContract(Contract):
    def approval_program(self) -> bool:
        dynamic_uint8_array = DynamicArray[UInt8](UInt8(1), UInt8(2))
        total = UInt64(0)
        for uint8_item in dynamic_uint8_array:
            total += uint8_item.decode()

        assert total == 3, "Total should be sum of dynamic_uint8_array items"
        aliased_dynamic = AliasedDynamicArray(UInt16(1))
        for uint16_item in aliased_dynamic:
            total += uint16_item.decode()
        assert total == 4, "Total should now include sum of aliased_dynamic items"
        dynamic_string_array = DynamicArray[String](String("Hello"), String("World"))
        assert dynamic_string_array.length == 2
        assert dynamic_string_array[0] == String("Hello")
        result = Bytes(b"")
        for index, string_item in uenumerate(dynamic_string_array):
            if index == 0:
                result = string_item.decode()
            else:
                result += b" " + string_item.decode()

        assert result == b"Hello World"

        static_uint32_array = StaticArray(UInt32(1), UInt32(10), UInt32(255), UInt32(128))

        for uint32_item in static_uint32_array:
            total += uint32_item.decode()

        assert total == 4 + 1 + 10 + 255 + 128

        aliased_static = AliasedStaticArray(UInt8(101))

        index = UInt64(0)

        assert (aliased_static[0].decode() + aliased_static[index].decode()) == 202

        static_string_array = StaticArray(String("Ping"), String("Pong"))

        result = Bytes(b"")
        for index, string_item in uenumerate(static_string_array):
            if index == 0:
                result = string_item.decode()
            else:
                result += b" " + string_item.decode()

        assert result == b"Ping Pong"

        return True

    def clear_state_program(self) -> bool:
        return True
