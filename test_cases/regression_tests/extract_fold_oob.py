from algopy import BaseContract, op


class ExtractLengthOOB(BaseContract):
    def approval_program(self) -> bool:
        # extract3: length extends past end of source (S+L > len)
        assert op.extract(b"\xab", 0, 5) == b"\xab"
        return True

    def clear_state_program(self) -> bool:
        return True


class ExtractStartOOB(BaseContract):
    def approval_program(self) -> bool:
        # extract3: start index beyond end of source (S > len)
        assert op.extract(b"\xab", 5, 1) == b""
        return True

    def clear_state_program(self) -> bool:
        return True


class SubstringEndOOB(BaseContract):
    def approval_program(self) -> bool:
        # substring3: end index beyond end of source (E > len)
        assert op.substring(b"\xab", 0, 5) == b"\xab"
        return True

    def clear_state_program(self) -> bool:
        return True
