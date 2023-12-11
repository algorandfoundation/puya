from puyapy import Contract, Bytes, subroutine


class MyContract(Contract):
    def approval_program(self) -> bool:
        assert is_in_str(
            Bytes(b"brown fox"), Bytes(b"The quick brown fox jumped over the lazy dog")
        )
        assert not is_in_str(
            Bytes(b"red fox"), Bytes(b"The quick brown fox jumped over the lazy dog")
        )

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def is_in_str(a: Bytes, b: Bytes) -> bool:
    return a in b
