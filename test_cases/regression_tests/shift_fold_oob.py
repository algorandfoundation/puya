from algopy import Contract, op


class ShlFoldOOB(Contract):
    def approval_program(self) -> bool:
        assert op.shl(1, 64) == 0
        return True

    def clear_state_program(self) -> bool:
        return True


class ShrFoldOOB(Contract):
    def approval_program(self) -> bool:
        assert op.shr(1, 64) == 0
        return True

    def clear_state_program(self) -> bool:
        return True
