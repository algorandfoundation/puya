from algopy import Contract, String, Txn


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

        alpha = String("abcdefg")
        assert alpha.startswith("")
        assert alpha.startswith("a")
        assert alpha.startswith("ab")
        assert not alpha.startswith("b")
        assert alpha.startswith(alpha)
        assert not alpha.startswith(alpha + "!")

        assert alpha.endswith("")
        assert alpha.endswith("g")
        assert alpha.endswith("fg")
        assert not alpha.endswith("f")
        assert alpha.endswith(alpha)
        assert not alpha.endswith("!" + alpha)

        d, e, f = String("d"), String("e"), String("f")
        assert String(".").join((d, e, f)) == "d.e.f"
        assert String(".").join((d, "e", f)) == "d.e.f"
        assert String(".").join(("d", "e", "f")) == "d.e.f"
        assert String(".").join(tuple("def")) == "d.e.f"
        assert String("").join((d, e, f)) == "def"
        assert String(".").join((d,)) == "d"
        assert String("").join((d,)) == "d"
        assert (
            String("args" if Txn.num_app_args else "no args") == "no args"
        ), "constructor expressions supported"

        return True

    def clear_state_program(self) -> bool:
        return True
