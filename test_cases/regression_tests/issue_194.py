from algopy import BaseContract, UInt64


class Issue194(BaseContract):
    # ref: https://github.com/algorandfoundation/puya/issues/194
    def approval_program(self) -> bool:
        assert bool(UInt64(1)) == bool(UInt64(2))
        two = UInt64(2)
        match bool(two):
            case True:
                return True
            case _:
                return False

    def clear_state_program(self) -> bool:
        return True
