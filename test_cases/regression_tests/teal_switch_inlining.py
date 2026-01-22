import algopy as a


class TealSwitchInlining(a.Contract):
    """Test for an issue introduced by TEAL block optimizations,
    whereby a target that is referenced multiple times by the same source block
    might be incorrectly inlined, when it should remain a labelled destination.
    """

    def approval_program(self) -> bool:
        match a.Txn.num_app_args:
            # at -O2, this block and the default block will be de-duplicated,
            # resulting in there being a reference to the default block in the `switch` cases
            # also, which cannot be inlined an must be preserved despite only having a single
            # predecessor block
            case 0:
                return True
            case 1:
                return False
            case _:
                return True

    def clear_state_program(self) -> bool:
        return True
