import typing as t

from algopy import Bytes, Contract, Txn, subroutine
from algopy.arc4 import (
    Bool as ARC4Bool,
    DynamicArray,
    StaticArray,
)


class Arc4BoolTypeContract(Contract):
    def approval_program(self) -> bool:
        self.test_stuff(ARC4Bool(True), ARC4Bool(False))
        assert ARC4Bool(
            False if Txn.num_app_args else True  # noqa: SIM211
        ).native, "conditional expr"

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

        dynamic_boolean_array = get_arr()
        dynamic_boolean_array.extend(
            (ARC4Bool(True), ARC4Bool(False), ARC4Bool(True), ARC4Bool(False), ARC4Bool(True))
        )
        assert dynamic_boolean_array.bytes == Bytes.from_hex("0005A8")

        assert ARC4Bool(True) == True  # noqa: E712
        assert ARC4Bool(False) != True  # noqa: E712
        assert False == ARC4Bool(False)  # noqa: E712, SIM300
        assert False != ARC4Bool(True)  # noqa: E712, SIM300

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


@subroutine(inline=False)
def get_arr() -> DynamicArray[ARC4Bool]:
    return DynamicArray[ARC4Bool]()
