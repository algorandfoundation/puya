from algopy import BaseContract, Bytes


class MyContract(BaseContract):
    def approval_program(self) -> bool:
        assert Bytes(b"brown fox") in Bytes(b"The quick brown fox jumped over the lazy dog")
        assert b"brown fox" in Bytes(b"The quick brown fox jumped over the lazy dog")
        assert Bytes(b"red fox") not in Bytes(b"The quick brown fox jumped over the lazy dog")
        assert b"red fox" not in Bytes(b"The quick brown fox jumped over the lazy dog")

        return True

    def clear_state_program(self) -> bool:
        return True
