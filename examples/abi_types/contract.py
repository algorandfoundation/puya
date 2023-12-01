import typing
import typing as t

from algopy import Bytes, Contract, UInt64
from algopy.arc4 import (
    DynamicArray,
    StaticArray,
    String,
    UInt8,
    UInt16,
    UInt32,
    UInt64 as ABIUInt64,
    UIntN,
)

AliasedDynamicArray: typing.TypeAlias = DynamicArray[UInt8]
AliasedStaticArray: typing.TypeAlias = StaticArray[UInt8, t.Literal[1]]


class AbiTypesContract(Contract):
    def approval_program(self) -> bool:
        some_bytes = Bytes(b"Hello World!")

        some_bytes_as_string = String.encode(some_bytes)

        some_bytes_as_bytes_again = some_bytes_as_string.decode()

        assert (
            some_bytes != some_bytes_as_string.bytes
        ), "Original bytes should not match encoded bytes"

        assert (
            some_bytes == some_bytes_as_string.bytes[2:]
        ), "Original bytes should match encoded if we strip the length header"

        assert some_bytes == some_bytes_as_bytes_again

        uint8 = UInt64(255)

        int8_encoded = UInt8.encode(uint8)

        int8_decoded = int8_encoded.decode()

        assert uint8 == int8_decoded

        test_bytes = Bytes.from_hex("7FFFFFFFFFFFFFFF00")
        assert UInt8.from_bytes(test_bytes).decode() == 2**8 - 1 - 2**7
        assert UIntN[typing.Literal[24]].from_bytes(test_bytes).decode() == 2**24 - 1 - 2**23
        assert UInt16.from_bytes(test_bytes).decode() == 2**16 - 1 - 2**15
        assert UInt32.from_bytes(test_bytes).decode() == 2**32 - 1 - 2**31
        assert ABIUInt64.from_bytes(test_bytes).decode() == 2**64 - 1 - 2**63

        dynamic_uint8_array = DynamicArray[UInt8](UInt8(1), UInt8(2))

        aliased_dynamic = AliasedDynamicArray(UInt8(1))

        dynamic_string_array = DynamicArray[String](String("Hello"), String("World"))

        static_uint8_array = StaticArray[UInt8, t.Literal[4]](
            UInt8(1), UInt8(10), UInt8(255), UInt8(128)
        )

        aliased_static = AliasedStaticArray(UInt8(1))

        static_string_array = StaticArray[String, t.Literal[2]](String("Ping"), String("Pong"))

        return True

    def clear_state_program(self) -> bool:
        return True
