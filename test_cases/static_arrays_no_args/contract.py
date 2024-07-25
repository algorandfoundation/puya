import typing

from algopy import Contract, Application, Asset, Account
from algopy.arc4 import (
    Address,
    Byte,
    DynamicArray,
    StaticArray,
    UInt32,
    UInt8,
    Struct,
    String,
    Bool,
)

AddressArray: typing.TypeAlias = StaticArray[Address, typing.Literal[2]]


class TestStruct(Struct):
    b_val: Bool
    u_val: UInt8
    s_val_1: String
    s_val_2: String


class TestContract(Contract):

    def approval_program(self) -> bool:
        assert StaticArray[Byte, typing.Literal[1]]() == StaticArray(Byte())
        assert AddressArray() == AddressArray(Address(), Address())

        assert StaticArray[AddressArray, typing.Literal[3]]() == StaticArray(
            AddressArray(), AddressArray(), AddressArray()
        )
        (a, b, c) = Application(), Asset(), Account()

        assert StaticArray[UInt32, typing.Literal[1]]() == StaticArray(UInt32())

        assert StaticArray[DynamicArray[AddressArray], typing.Literal[1]]() == StaticArray(
            DynamicArray[AddressArray]()
        )
        # TODO: The following should either work, or fail gracefully
        # x = StaticArray[TestStruct, typing.Literal[4]]()
        # assert StaticArray[TestContract, typing.Literal[4]]() == StaticArray(
        #     TestStruct(), TestStruct(), TestStruct(), TestStruct()
        # )

        return True

    def clear_state_program(self) -> bool:
        return True
