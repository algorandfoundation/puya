from puyapy import Contract, String, subroutine


class StringContract(Contract):
    def approval_program(self) -> bool:
        empty = String()
        assert not empty, "Empty bytes should be False"
        non_empty = String(" ")
        assert non_empty, "Non-empty bytes should be True"

        assert String("a") + "b" == "ab"
        assert String("a") + "b" == String("ab")
        assert "a" + String("b") == String("ab")

        assert empty != non_empty

        c = String("c")
        c += "d"
        c += String("e")
        assert c == "cde"

        assert "brown fox" in String("The quick brown fox jumped over the lazy dog")
        assert String("red fox") not in String("The quick brown fox jumped over the lazy dog")

        return True

    def clear_state_program(self) -> bool:
        return True
