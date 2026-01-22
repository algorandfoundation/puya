import typing as t

from algopy import Bytes, Contract, String, UInt64, op, subroutine, uenumerate
from algopy.arc4 import (
    Byte,
    DynamicArray,
    StaticArray,
    String as ARC4String,
    UFixedNxM,
    UInt8,
    UInt16,
    UInt32,
)

AliasedDynamicArray: t.TypeAlias = DynamicArray[UInt16]
AliasedStaticArray: t.TypeAlias = StaticArray[UInt8, t.Literal[1]]

Decimal: t.TypeAlias = UFixedNxM[t.Literal[64], t.Literal[10]]

HashResult: t.TypeAlias = StaticArray[Byte, t.Literal[32]]


class Arc4ArraysContract(Contract):
    def approval_program(self) -> bool:
        dynamic_uint8_array = DynamicArray[UInt8](UInt8(1), UInt8(2))
        total = UInt64(0)
        for uint8_item in dynamic_uint8_array:
            total += uint8_item.as_uint64()

        assert total == 3, "Total should be sum of dynamic_uint8_array items"
        aliased_dynamic = AliasedDynamicArray(UInt16(1))
        for uint16_item in aliased_dynamic:
            total += uint16_item.as_uint64()
        assert total == 4, "Total should now include sum of aliased_dynamic items"
        dynamic_string_array = DynamicArray[ARC4String](ARC4String("Hello"), ARC4String("World"))
        assert dynamic_string_array.length == 2
        assert dynamic_string_array[0] == ARC4String("Hello")
        result = String("")
        for index, string_item in uenumerate(dynamic_string_array):
            if index == 0:
                result = string_item.native
            else:
                result += " " + string_item.native

        assert result == "Hello World"

        static_uint32_array = StaticArray(UInt32(1), UInt32(10), UInt32(255), UInt32(128))

        for uint32_item in static_uint32_array:
            total += uint32_item.as_uint64()
        assert total == 4 + 1 + 10 + 255 + 128

        static_uint8_array = StaticArray[UInt8, t.Literal[4]].from_bytes(
            b"\x01\x02\x03\x04\x05\x06"
        )
        uint8_total = UInt64(0)
        count = UInt64(0)
        for uint8_item in static_uint8_array:
            uint8_total += uint8_item.as_uint64()
            count += UInt64(1)
        assert uint8_total == 1 + 2 + 3 + 4
        assert count == 4

        aliased_static = AliasedStaticArray(UInt8(101))

        index = UInt64(0)

        assert (aliased_static[0].as_uint64() + aliased_static[index].as_uint64()) == 202

        static_string_array = StaticArray(ARC4String("Ping"), ARC4String("Pong"))

        result = String("")
        for index, string_item in uenumerate(static_string_array):
            if index == 0:
                result = string_item.native
            else:
                result += " " + string_item.native

        assert result == "Ping Pong"

        static_string_array[1] = ARC4String("Ping")
        result = String()
        for string_item in static_string_array:
            result += string_item.native + " "
        assert result == "Ping Ping "

        self.hash_as_array(Bytes(b"Testing 123"))

        return True

    @subroutine
    def hash_as_array(self, commitment_args_concat: Bytes) -> HashResult:
        return HashResult.from_bytes(op.sha3_256(commitment_args_concat))

    def clear_state_program(self) -> bool:
        return True
