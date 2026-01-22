from algopy import Contract, UInt64, op


class GetBitFoldOOBBytes(Contract):
    def approval_program(self) -> bool:
        # out of bounds bit index access (8 bits, indices 0...7)
        assert op.getbit(b"\xff", 8) == UInt64(0)
        return True

    def clear_state_program(self) -> bool:
        return True
