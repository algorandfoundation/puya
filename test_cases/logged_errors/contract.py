from algopy import String, UInt64, arc4, op
from algopy.arc4 import ARC4Contract


class ArrayAccessContract(ARC4Contract):
    @arc4.abimethod
    def test_branching_array_call(self, arg: UInt64) -> None:
        assert arg != 0, "regular arc56 error not logged"
        assert arg != 1, String("this error should be logged with warnings")

        non_const_string: String = String(str(op.itob(arg))) + String(
            "non constant string should be logged with warnings"
        )
        assert arg != 2, non_const_string
