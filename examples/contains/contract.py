from algopy import BigUInt, Bytes, Contract, UInt64, subroutine


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        not_ten = UInt64(15)

        one_true = self.is_in_tuple_1(UInt64(10), (UInt64(10), not_ten, Bytes(b"five")))
        one_false = self.is_in_tuple_1(UInt64(5), (UInt64(10), not_ten, Bytes(b"five")))
        assert one_true, "Should be true"
        assert not one_false, "Should be false"

        two_true = self.is_in_tuple_2(
            Bytes(b"hello"), (Bytes(b"hello"), UInt64(0), Bytes(b"bonjour"))
        )
        two_false = self.is_in_tuple_2(
            Bytes(b"ciao"), (Bytes(b"hello"), UInt64(0), Bytes(b"bonjour"))
        )
        assert two_true, "Should be true"
        assert not two_false, "Should be false"

        three_true = self.is_in_tuple_3(
            BigUInt(32323423423423), (BigUInt(32323423423423), BigUInt(8439439483934))
        )
        three_false = self.is_in_tuple_3(
            BigUInt(32323423423423) + BigUInt(32323423423423),
            (BigUInt(32323423423423), BigUInt(8439439483934)),
        )
        assert three_true, "Should be true"
        assert not three_false, "Should be false"

        return UInt64(1)

    def clear_state_program(self) -> UInt64:
        return UInt64(1)

    @subroutine
    def is_in_tuple_1(self, x: UInt64, y: tuple[UInt64, UInt64, Bytes]) -> bool:
        return x in y

    @subroutine
    def is_in_tuple_2(self, x: Bytes, y: tuple[Bytes, UInt64, Bytes]) -> bool:
        return x in y

    @subroutine
    def is_in_tuple_3(self, x: BigUInt, y: tuple[BigUInt, BigUInt]) -> bool:
        return x in y
