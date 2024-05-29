import typing

from algopy import ARC4Contract, arc4, log, subroutine


class StaticStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.StaticArray[arc4.Byte, typing.Literal[2]]


class DynamicStruct(arc4.Struct):
    a: arc4.String
    b: arc4.String


class MixedSingleStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.String
    c: arc4.UInt64


class MixedMultipleStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.String
    c: arc4.UInt64
    d: arc4.String
    e: arc4.UInt64


class DynamicArrayContract(ARC4Contract):

    @arc4.abimethod()
    def test_static_elements(self) -> None:
        byte_array1 = arc4.StaticArray(get_byte1(), get_byte2())
        byte_array2 = arc4.StaticArray(get_byte3(), get_byte4())

        struct1 = StaticStruct(get_uint1(), byte_array1)
        struct2 = StaticStruct(get_uint2(), byte_array2)
        array = arc4.DynamicArray(struct1.copy(), struct2.copy())
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1

    @arc4.abimethod()
    def test_dynamic_elements(self) -> None:
        struct1 = DynamicStruct(get_string1(), get_string2())
        struct2 = DynamicStruct(get_string3(), get_string1())
        array = arc4.DynamicArray(struct1.copy(), struct2.copy())
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1

    @arc4.abimethod()
    def test_mixed_single_dynamic_elements(self) -> None:
        struct1 = MixedSingleStruct(get_uint1(), get_string1(), get_uint2())
        struct2 = MixedSingleStruct(get_uint2(), get_string2(), get_uint1())
        array = arc4.DynamicArray(struct1.copy(), struct2.copy())
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1

    @arc4.abimethod()
    def test_mixed_multiple_dynamic_elements(self) -> None:
        struct1 = MixedMultipleStruct(
            get_uint1(), get_string1(), get_uint2(), get_string2(), get_uint1()
        )
        struct2 = MixedMultipleStruct(
            get_uint2(), get_string3(), get_uint1(), get_string1(), get_uint2()
        )
        array = arc4.DynamicArray(struct1.copy(), struct2.copy())
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1


@subroutine
def get_string1() -> arc4.String:
    return arc4.String("a")


@subroutine
def get_string2() -> arc4.String:
    return arc4.String("bee")


@subroutine
def get_string3() -> arc4.String:
    return arc4.String("Hello World")


@subroutine
def get_uint1() -> arc4.UInt64:
    return arc4.UInt64(3)


@subroutine
def get_uint2() -> arc4.UInt64:
    return arc4.UInt64(2**42)


@subroutine
def get_byte1() -> arc4.Byte:
    return arc4.Byte(4)


@subroutine
def get_byte2() -> arc4.Byte:
    return arc4.Byte(5)


@subroutine
def get_byte3() -> arc4.Byte:
    return arc4.Byte(42)


@subroutine
def get_byte4() -> arc4.Byte:
    return arc4.Byte(255)
