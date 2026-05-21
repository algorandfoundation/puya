from algopy import Contract, GlobalState, UInt64, op


class SwitchCaseKeyCollision(Contract):
    def __init__(self) -> None:
        self.glob = GlobalState(UInt64)

    def approval_program(self) -> bool:
        x = op.Txn.num_app_args + UInt64(5)

        # here when x=5, per python semantics we should go into
        # the first branch regardless of the value of `glob`
        self.glob.value = UInt64(5)
        match x:
            case 5:
                val = UInt64(1)
            case self.glob.value:
                val = UInt64(2)
            case _:
                val = UInt64(3)
        assert val == 1, "case 5 must win"

        return True

    def clear_state_program(self) -> bool:
        return True
