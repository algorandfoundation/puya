import typing

from algopy import Contract, UInt64, subroutine
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

        my_array_copy_3 = my_array_copy.copy()

        originals = (my_array.copy(), my_array_copy_2.copy(), my_array_copy_3.copy())
        self.mutate_tuple_items_and_reassign(
            (my_array.copy(), my_array_copy_2.copy(), my_array_copy_3.copy()),
            start=UInt64(0),
            reassign=True,
        )
        assert originals == (my_array, my_array_copy_2, my_array_copy_3)

        self.mutate_tuple_items_and_reassign(
            (my_array, my_array_copy_2, my_array_copy_3), start=UInt64(100), reassign=True
        )

        assert my_array[0] == 100
        assert my_array_copy_2[0] == 101
        assert my_array_copy_3[0] == 102
        assert my_array[1] == 103
        assert my_array_copy_2[1] == 104
        assert my_array_copy_3[1] == 105

        self.mutate_tuple_items_and_reassign(
            (my_array, my_array_copy_2, my_array_copy_3), start=UInt64(200), reassign=False
        )

        assert my_array[0] == 200
        assert my_array_copy_2[0] == 201
        assert my_array_copy_3[0] == 202
        assert my_array[1] == 206
        assert my_array_copy_2[1] == 207
        assert my_array_copy_3[1] == 208

        foo = (my_array.copy(), my_array.copy(), my_array.copy())
        self.mutate_tuple_items_and_reassign(foo, start=UInt64(222), reassign=False)
        assert foo[0][1] == (306 - 78)
        assert foo[1][1] == (307 - 78)
        assert foo[2][1] == (308 - 78)

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
    def mutate_tuple_items_and_reassign(
        self, arrays: tuple[TestArray, TestArray, TestArray], *, start: UInt64, reassign: bool
    ) -> None:
        arrays[0][0] = UInt8(start)
        arrays[1][0] = UInt8(start + 1)
        arrays[2][0] = UInt8(start + 2)

        assert arrays[0][0] == start
        assert arrays[1][0] == start + 1
        assert arrays[2][0] == start + 2

        arrays[0][1] = UInt8(start + 3)
        arrays[1][1] = UInt8(start + 4)
        arrays[2][1] = UInt8(start + 5)

        # overwrite params
        if reassign:
            arrays = (arrays[0].copy(), arrays[1].copy(), arrays[2].copy())

        arrays[0][1] = UInt8(start + 6)
        arrays[1][1] = UInt8(start + 7)
        arrays[2][1] = UInt8(start + 8)

        assert arrays[0][1] == start + 6
        assert arrays[1][1] == start + 7
        assert arrays[2][1] == start + 8

    def clear_state_program(self) -> bool:
        return True
