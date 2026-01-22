from algopy import Contract, op


class ReplaceFoldOOB(Contract):
    def approval_program(self) -> bool:
        assert op.replace(b"", 0, b"abc") == b"abc"
        return True

    def clear_state_program(self) -> bool:
        return True
