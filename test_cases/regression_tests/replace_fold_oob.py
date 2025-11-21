from algopy import BaseContract, op


class ReplaceFoldOOB(BaseContract):
    def approval_program(self) -> bool:
        assert op.replace(b"", 0, b"abc") == b"abc"
        return True

    def clear_state_program(self) -> bool:
        return True
