from algopy import BaseContract, op


class GetBitFoldOOBUInt64(BaseContract):
    def approval_program(self) -> bool:
        # out of bounds bit index access (should be indices 0...63)
        assert op.getbit(0, 64) == 0
        return True

    def clear_state_program(self) -> bool:
        return True
