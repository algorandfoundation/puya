import typing

from algopy import Contract, subroutine
from algopy.arc4 import (
    Bool,
    StaticArray,
    String,
    Struct,
    UInt8,
)


class TestStruct(Struct):
    b_val: Bool
    u_val: UInt8
    s_val_1: String
    s_val_2: String


TestArray: typing.TypeAlias = StaticArray[UInt8, typing.Literal[4]]


class StructWithArray(Struct):
    test_array: TestArray


class Arc4MutableParamsContract(Contract):
    def approval_program(self) -> bool:
        self.mutating_copies()

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
        my_struct_copy = my_struct.copy()

        my_array[2] = UInt8(5)

        assert my_array_copy[2] == UInt8(3), "my_array_copy should be unchanged"
        assert my_array[2] == UInt8(5), "my_array should be mutated"

        # Pass to subroutine without a copy
        t, f = self.other_routine(my_array, my_struct)
        assert t
        assert not f

        assert my_array[1] == UInt8(5), "my_array has been mutated by the subroutine"

        assert my_struct.s_val_1 == String(
            "AARRGH!"
        ), "my_struct has been mutated by the subroutine"

        # Pass to subroutine with copy
        self.other_routine(my_array_copy.copy(), my_struct_copy.copy())

        assert my_array_copy[1] == UInt8(
            2
        ), "my_array_copy should not be mutated by the subroutine"

        assert my_struct_copy.s_val_1 == String(
            "Happy"
        ), "my_struct_copy should not be mutated by the subroutine"

        my_array_copy_2 = my_array_copy.copy()

        my_array_copy_2 = self.other_routine_2(my_array_copy_2)

        assert my_array_copy_2[0] == UInt8(1), "my_array_copy_2 should have original value"

        self.other_routine_2(my_array_copy_2)
        assert my_array_copy_2[0] == UInt8(10), "my_array_copy_2 should have mutated value"

        # This is commented out because mutable params do not work with tuples
        # self.other_routine_3((my_array, my_array_copy_2, my_array_copy_2))
        #
        # assert my_array[0] == my_array_copy_2[0] == my_array_copy[0] == UInt8(99), \
        #     "All arrays should be mutated"

        # Nested array items should still require a copy
        nested = StructWithArray(test_array=my_array.copy())
        self.other_routine_2(nested.test_array.copy())

    @subroutine
    def other_routine(self, array: TestArray, struct: TestStruct) -> tuple[bool, bool]:
        array[1] = UInt8(5)
        struct.s_val_1 = String("AARRGH!")
        return True, False

    @subroutine
    def other_routine_2(self, array: TestArray) -> TestArray:
        copy = array.copy()
        array[0] = UInt8(10)
        return copy

    @subroutine
    def other_routine_3(self, arrays: tuple[TestArray, TestArray, TestArray]) -> None:
        # This doesn't mutate the params
        for array in arrays:
            array[0] = UInt8(99)

        # This also doesn't work
        arrays[0][0] = UInt8(99)
        arrays[1][0] = UInt8(99)
        arrays[2][0] = UInt8(99)

        # And this doesn't work
        (one, two, three) = arrays
        one[0] = UInt8(99)
        two[0] = UInt8(99)
        three[0] = UInt8(99)

    def clear_state_program(self) -> bool:
        return True
