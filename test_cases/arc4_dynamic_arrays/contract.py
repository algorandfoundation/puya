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
    d: arc4.DynamicArray[arc4.UInt16]
    e: arc4.UInt64


class NestedDynamicStruct(arc4.Struct):
    one: StaticStruct
    two: DynamicStruct
    three: StaticStruct
    four: MixedMultipleStruct
    five: DynamicStruct


class DynamicArrayContract(ARC4Contract):
    @arc4.abimethod()
    def test_static_elements(self) -> None:
        byte_array1 = arc4.StaticArray(get_byte1(), get_byte2())
        byte_array2 = arc4.StaticArray(get_byte3(), get_byte4())

        struct1 = StaticStruct(get_uint1(), byte_array1.copy())
        struct2 = StaticStruct(get_uint2(), byte_array2.copy())
        array = arc4.DynamicArray(struct1.copy(), struct1.copy())
        array[1] = struct2.copy()
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1

    @arc4.abimethod()
    def test_dynamic_elements(self) -> None:
        struct1 = DynamicStruct(get_string1(), get_string2())
        struct2 = DynamicStruct(get_string3(), get_string1())
        array = arc4.DynamicArray(struct1.copy(), struct1.copy())
        array.append(struct1.copy())
        array[1] = struct2.copy()  # replace
        log(array)
        log(array[0])
        log(array[1])
        log(array[2])

        assert array.pop() == struct1
        log(array)
        assert array.pop() == struct2
        log(array)
        assert array.pop() == struct1
        log(array)

    @arc4.abimethod()
    def test_mixed_single_dynamic_elements(self) -> None:
        struct1 = MixedSingleStruct(get_uint1(), get_string1(), get_uint2())
        struct2 = MixedSingleStruct(get_uint2(), get_string2(), get_uint1())
        array = arc4.DynamicArray[MixedSingleStruct]()
        array.append(struct2.copy())
        array.append(struct2.copy())
        array[0] = struct1.copy()  # replace
        log(array)
        log(array[0])
        log(array[1])

        array2 = array.copy()

        assert array.pop() == struct2
        assert array.pop() == struct1

        assert array2.length == 2
        array2.extend(array2.copy())
        assert array2.length == 4
        assert array2[-1] == struct2
        assert array2[-2] == struct1

    @arc4.abimethod()
    def test_mixed_multiple_dynamic_elements(self) -> None:
        struct1 = MixedMultipleStruct(
            get_uint1(), get_string1(), get_uint2(), get_u16_arr1(), get_uint1()
        )
        struct2 = MixedMultipleStruct(
            get_uint2(), get_string2(), get_uint1(), get_u16_arr2(), get_uint2()
        )
        array = arc4.DynamicArray(struct1.copy(), struct1.copy())
        array[1] = struct2.copy()
        log(array)
        log(array[0])
        log(array[1])

        assert array.pop() == struct2
        assert array.pop() == struct1

    @arc4.abimethod()
    def test_nested_struct_replacement(self) -> None:
        one = StaticStruct(get_uint1(), arc4.StaticArray(get_byte1(), get_byte2()))
        two = DynamicStruct(get_string1(), get_string2())
        three = StaticStruct(get_uint2(), arc4.StaticArray(get_byte2(), get_byte1()))
        four = MixedMultipleStruct(
            get_uint1(), get_string1(), get_uint2(), get_u16_arr1(), get_uint1()
        )
        five = DynamicStruct(get_string1(), get_string2())
        struct1 = NestedDynamicStruct(
            one=one.copy(),
            two=two.copy(),
            three=three.copy(),
            four=four.copy(),
            five=five.copy(),
        )
        struct2 = NestedDynamicStruct(
            one=one.copy(),
            two=DynamicStruct(get_string2(), get_string1()),  # this is the difference with struct1
            three=three.copy(),
            four=four.copy(),
            five=five.copy(),
        )

        struct2.two = two.copy()  # now struct2 should match struct1
        assert struct1.bytes == struct2.bytes, "struct1 does not match struct2"

    @arc4.abimethod()
    def test_nested_tuple_modification(self) -> None:
        one = StaticStruct(get_uint1(), arc4.StaticArray(get_byte1(), get_byte2()))
        two = DynamicStruct(get_string1(), get_string2())
        three = StaticStruct(get_uint2(), arc4.StaticArray(get_byte2(), get_byte1()))
        four1 = MixedMultipleStruct(
            get_uint1(), get_string1(), get_uint2(), get_u16_arr1(), get_uint1()
        )
        four2 = MixedMultipleStruct(
            get_uint1(),
            get_string1(),
            get_uint2(),
            get_u16_arr1() + (arc4.UInt16(123),),  # noqa: RUF005
            get_uint1(),
        )
        five = DynamicStruct(get_string1(), get_string2())
        tup1 = arc4.Tuple(
            (
                one.copy(),
                two.copy(),
                three.copy(),
                four1.copy(),
                five.copy(),
            )
        )
        tup2 = arc4.Tuple(
            (
                one.copy(),
                two.copy(),
                three.copy(),
                four2.copy(),
                five.copy(),
            )
        )

        tup2[3].d.pop()
        assert tup1.bytes == tup2.bytes, "tup1 does not match tup2"


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


@subroutine
def get_u16_arr1() -> arc4.DynamicArray[arc4.UInt16]:
    return arc4.DynamicArray(arc4.UInt16(2**16 - 1), arc4.UInt16(0), arc4.UInt16(42))


@subroutine
def get_u16_arr2() -> arc4.DynamicArray[arc4.UInt16]:
    return arc4.DynamicArray(arc4.UInt16(1), arc4.UInt16(2), arc4.UInt16(3), arc4.UInt16(4))
