import typing
import typing as t

from puyapy import Bytes, Contract, subroutine
from puyapy.arc4 import (
    Bool,
    DynamicArray,
    StaticArray,
    String,
    Struct,
    UFixedNxM,
    UInt8,
    UInt16,
)

AliasedDynamicArray: t.TypeAlias = DynamicArray[UInt16]
AliasedStaticArray: t.TypeAlias = StaticArray[UInt8, t.Literal[1]]

Decimal: t.TypeAlias = UFixedNxM[t.Literal[64], t.Literal[10]]


class TestStruct(Struct):
    b_val: Bool
    u_val: UInt8
    s_val_1: String
    s_val_2: String


class Arc4MutationContract(Contract):
    def approval_program(self) -> bool:
        self.dynamic_array_fixed_size()
        self.dynamic_array_bool()
        self.dynamic_array_string()
        self.array_of_array_dynamic()
        self.array_of_array_static()
        self.index_assign()
        self.struct_assign()
        self.array_concat()
        return True

    @subroutine
    def mutating_copies(self) -> None:
        my_array = StaticArray(UInt8(1), UInt8(2), UInt8(3), UInt8(4))
        my_struct = TestStruct(
            b_val=Bool(True),
            u_val=UInt8(50),
            s_val_1=String("Happy"),
            s_val_2=String("Days"),
        )

        my_array_copy = my_array.copy()

        my_array[2] = UInt8(5)

        assert my_array_copy[2] == UInt8(5)

        self.other_routine(my_array.copy(), my_struct.copy())

        assert my_array[1] == UInt8(2)
        assert my_array_copy[1] == UInt8(2)
        assert my_struct.s_val_1 == String("Happy")

    @subroutine
    def other_routine(
        self, array: StaticArray[UInt8, typing.Literal[4]], struct: TestStruct
    ) -> None:
        array[1] = UInt8(5)
        struct.s_val_1 = String("AARRGH!")

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def array_concat(self) -> None:
        uint8_array = DynamicArray(UInt8(1), UInt8(2))
        array_concat_tuple = uint8_array + (UInt8(3), UInt8(4))  # noqa: RUF005
        assert array_concat_tuple == DynamicArray(UInt8(1), UInt8(2), UInt8(3), UInt8(4))
        array_concat_tuple += (UInt8(5),)
        assert array_concat_tuple == DynamicArray(UInt8(1), UInt8(2), UInt8(3), UInt8(4), UInt8(5))

        hello_world = DynamicArray(String("Hello"), String("World"))
        hello_world_concat = DynamicArray(String("Hello")) + DynamicArray(String("World"))
        assert hello_world == hello_world_concat

    @subroutine
    def array_of_array_dynamic(self) -> None:
        array_of_array = DynamicArray[DynamicArray[UInt8]]()
        assert array_of_array.bytes == Bytes.from_hex("0000")
        array_of_array.append(DynamicArray[UInt8](UInt8(10)))
        assert array_of_array.bytes == Bytes.from_hex("0001000200010A")
        array_of_array.append(DynamicArray[UInt8](UInt8(16)))
        assert array_of_array.bytes == Bytes.from_hex("00020004000700010A000110")
        array_of_array[0].append(UInt8(255))

        assert array_of_array.bytes == Bytes.from_hex("00020004000800020AFF000110")

        array_of_array[0][1] = UInt8(0)
        assert array_of_array.bytes == Bytes.from_hex("00020004000800020A00000110")

    @subroutine
    def array_of_array_static(self) -> None:
        array_of_array = StaticArray[StaticArray[UInt8, typing.Literal[2]], typing.Literal[2]](
            StaticArray[UInt8, typing.Literal[2]](UInt8(10), UInt8(9)),
            StaticArray[UInt8, typing.Literal[2]](UInt8(64), UInt8(128)),
        )

        assert array_of_array.bytes == Bytes.from_hex("0A094080")

        array_of_array[0] = StaticArray[UInt8, typing.Literal[2]](UInt8(255), UInt8(254))
        assert array_of_array.bytes == Bytes.from_hex("FFFE4080")

        array_of_array[1][0] = UInt8(1)
        assert array_of_array.bytes == Bytes.from_hex("FFFE0180")

    @subroutine
    def index_assign(self) -> None:
        dynamic_uint8_array = DynamicArray[UInt8](UInt8(1), UInt8(2))
        dynamic_uint8_array[0] = UInt8(255)
        assert dynamic_uint8_array.bytes == Bytes.from_hex("0002ff02")
        static_uint8_array = StaticArray(UInt8(1), UInt8(2))
        static_uint8_array[1] = UInt8(255)
        assert static_uint8_array.bytes == Bytes.from_hex("01ff")

        dynamic_bool_array = DynamicArray(Bool(True), Bool(False))
        dynamic_bool_array[0] = Bool(False)
        assert dynamic_bool_array.bytes == Bytes.from_hex("000200")
        static_bool_array = StaticArray[Bool, typing.Literal[2]](Bool(True), Bool(True))
        static_bool_array[1] = Bool(False)
        assert static_bool_array.bytes == Bytes.from_hex("80")

    @subroutine
    def struct_assign(self) -> None:
        test_struct = TestStruct(
            b_val=Bool(True),
            u_val=UInt8(50),
            s_val_1=String("Happy"),
            s_val_2=String("Days"),
        )

        test_struct.b_val = Bool(False)
        test_struct.u_val = UInt8(12)
        assert test_struct == TestStruct(
            b_val=Bool(False),
            u_val=UInt8(12),
            s_val_1=String("Happy"),
            s_val_2=String("Days"),
        )
        test_struct.s_val_1 = String("Hmmmm")
        test_struct.s_val_2 = String("Oh well")

        assert test_struct == TestStruct(
            b_val=Bool(False),
            u_val=UInt8(12),
            s_val_1=String("Hmmmm"),
            s_val_2=String("Oh well"),
        )

    @subroutine
    def dynamic_array_fixed_size(self) -> None:
        dynamic_uint8_array = DynamicArray[UInt8](UInt8(1), UInt8(2))
        dynamic_uint8_array.append(UInt8(50))
        assert dynamic_uint8_array == DynamicArray[UInt8](UInt8(1), UInt8(2), UInt8(50))
        dynamic_uint8_array.extend(dynamic_uint8_array)

        assert dynamic_uint8_array == DynamicArray[UInt8](
            UInt8(1), UInt8(2), UInt8(50), UInt8(1), UInt8(2), UInt8(50)
        )
        dynamic_uint8_array.extend((UInt8(4), UInt8(90)))

        assert dynamic_uint8_array == DynamicArray(
            UInt8(1), UInt8(2), UInt8(50), UInt8(1), UInt8(2), UInt8(50), UInt8(4), UInt8(90)
        )

        popped = dynamic_uint8_array.pop()
        assert popped == UInt8(90)

        assert dynamic_uint8_array == DynamicArray(
            UInt8(1), UInt8(2), UInt8(50), UInt8(1), UInt8(2), UInt8(50), UInt8(4)
        )

    @subroutine
    def dynamic_array_bool(self) -> None:
        dynamic_bool_array = DynamicArray[Bool](Bool(True), Bool(False))
        assert dynamic_bool_array.bytes == Bytes.from_hex("000280")
        dynamic_bool_array.extend((Bool(True), Bool(False)))
        assert dynamic_bool_array.bytes == Bytes.from_hex("0004A0")
        assert dynamic_bool_array == DynamicArray[Bool](
            Bool(True), Bool(False), Bool(True), Bool(False)
        )
        dynamic_bool_array.extend(dynamic_bool_array)

        assert dynamic_bool_array == DynamicArray[Bool](
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
        )
        dynamic_bool_array.append(Bool(True))

        assert dynamic_bool_array == DynamicArray[Bool](
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
        )

        assert dynamic_bool_array.pop() == Bool(True)
        assert dynamic_bool_array.pop() == Bool(False)
        assert dynamic_bool_array == DynamicArray[Bool](
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
            Bool(False),
            Bool(True),
        )

    @subroutine
    def dynamic_array_string(self) -> None:
        hello = String("Hello")
        world = String("World")
        foo = String("Foo")
        bar = String("Bar")
        dynamic_string_array = DynamicArray(hello, world)
        assert dynamic_string_array.bytes == Bytes(
            b"\x00\x02\x00\x04\x00\x0b\x00\x05Hello\x00\x05World"
        )
        dynamic_string_array.extend((foo, bar))

        assert dynamic_string_array.bytes == Bytes(
            b"\x00\x04\x00\x08\x00\x0f\x00\x16\x00\x1b\x00\x05Hello\x00\x05World\x00\x03Foo\x00\x03Bar"
        )

        dynamic_string_array.extend(dynamic_string_array)

        assert dynamic_string_array == DynamicArray(hello, world, foo, bar, hello, world, foo, bar)
        dynamic_string_array = DynamicArray(hello, world, foo, bar, hello, world, foo, bar)
        dynamic_string_array[3] = hello
        dynamic_string_array[5] = hello

        assert dynamic_string_array == DynamicArray(
            hello, world, foo, hello, hello, hello, foo, bar
        )

        assert dynamic_string_array.pop() == bar
        assert dynamic_string_array.pop() == foo
        assert dynamic_string_array == DynamicArray(hello, world, foo, hello, hello, hello)
