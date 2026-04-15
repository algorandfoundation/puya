from algopy import Contract, UInt64, op


class GetBitFoldOOBUInt64(Contract):
    def approval_program(self) -> bool:
        # out of bounds bit index access (should be indices 0...63)
        assert op.getbit(UInt64(0), 64) == UInt64(0)
        return True

    def clear_state_program(self) -> bool:
        return True
