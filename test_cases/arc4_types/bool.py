import typing as t

from algopy import Bytes, Contract, subroutine
from algopy.arc4 import (
    Bool as ARC4Bool,
    DynamicArray,
    StaticArray,
)


class Arc4BoolTypeContract(Contract):
    def approval_program(self) -> bool:
        self.test_stuff(ARC4Bool(True), ARC4Bool(False))

        static_boolean_array = StaticArray[ARC4Bool, t.Literal[12]](
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
            ARC4Bool(True),
        )

        assert static_boolean_array.bytes == Bytes.from_hex("FFF0")

        assert static_boolean_array[0] == ARC4Bool(True), "Single boolean can be unpacked"
        assert static_boolean_array[-1] == ARC4Bool(True), "Single boolean can be unpacked"

        dynamic_boolean_array = DynamicArray[ARC4Bool](
            ARC4Bool(True), ARC4Bool(False), ARC4Bool(True)
        )

        assert dynamic_boolean_array.bytes == Bytes.from_hex("0003A0")

        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def test_stuff(self, true: ARC4Bool, false: ARC4Bool) -> bool:
        assert true.native

        assert not false.native

        assert true == ARC4Bool(true.native)
        assert false == ARC4Bool(false.native)

        return true.native
