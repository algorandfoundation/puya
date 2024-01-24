from puyapy import Bytes, Contract, Scratch, UInt64, urange


class MyContract(Contract, scratch_slots=(1, 2, urange(3, 20))):
    def approval_program(self) -> bool:
        Scratch.store(1, UInt64(5))

        Scratch.store(2, Bytes(b"Hello World"))

        for i in urange(3, 20):
            Scratch.store(i, i)

        assert Scratch.load_uint64(1) == UInt64(5)

        assert Scratch.load_bytes(2) == b"Hello World"

        assert Scratch.load_uint64(5) == UInt64(5)
        return True

    def clear_state_program(self) -> bool:
        return True
