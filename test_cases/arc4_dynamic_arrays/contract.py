import typing

from algopy import Contract, arc4, log


class DynamicStruct(arc4.Struct):
    a: arc4.String
    b: arc4.String


class FixedStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.StaticArray[arc4.Byte, typing.Literal[2]]


class MixedStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.String
    c: arc4.UInt64


class DynamicArrayContract(Contract):

    def approval_program(self) -> bool:
        string1 = arc4.String("aye")
        string2 = arc4.String("bee")
        string3 = arc4.String("Hello")
        uint1 = arc4.UInt64(3)
        uint2 = arc4.UInt64(2**42)
        byte_array1 = arc4.StaticArray(arc4.Byte(4), arc4.Byte(5))
        byte_array2 = arc4.StaticArray(arc4.Byte(42), arc4.Byte(80))

        dynamic_struct1 = DynamicStruct(string1, string2)
        dynamic_struct2 = DynamicStruct(string3, string1)
        dynamic_array = arc4.DynamicArray(dynamic_struct1.copy(), dynamic_struct2.copy())
        log(dynamic_array)
        log(dynamic_array[0])
        log(dynamic_array[1])

        fixed1 = FixedStruct(uint1, byte_array1)
        fixed2 = FixedStruct(uint2, byte_array2)
        dynamic_fixed = arc4.DynamicArray(fixed1.copy(), fixed2.copy())
        log(dynamic_fixed)
        log(dynamic_fixed[0])
        log(dynamic_fixed[1])

        mixed1 = MixedStruct(uint1, string1, uint2)
        mixed2 = MixedStruct(uint2, string2, uint1)
        dynamic_mixed = arc4.DynamicArray(mixed1.copy(), mixed2.copy())
        log(dynamic_mixed)
        log(dynamic_mixed[0])
        log(dynamic_mixed[1])

        return True

    def clear_state_program(self) -> bool:
        return True
