from puyapy import Bytes, Contract, UInt64, op, urange

TWO = 2
TWENTY = 20


class MyContract(Contract, scratch_slots=(1, TWO, urange(3, TWENTY))):
    def approval_program(self) -> bool:
        op.Scratch.store(1, UInt64(5))

        op.Scratch.store(2, Bytes(b"Hello World"))

        for i in urange(3, 20):
            op.Scratch.store(i, i)

        assert op.Scratch.load_uint64(1) == UInt64(5)

        assert op.Scratch.load_bytes(2) == b"Hello World"

        assert op.Scratch.load_uint64(5) == UInt64(5)
        return True

    def clear_state_program(self) -> bool:
        return True
