from algopy import Contract, op


class SetBitFoldOOBUInt64(Contract):
    def approval_program(self) -> bool:
        # out of bounds bit index write (valid indices are 0...63 for uint64)
        # value=True case: folding produces source | (1 << 64), exceeding uint64 range
        assert op.setbit_uint64(0, 64, True) == 0
        # value=False case: folding silently returns source unchanged instead of panicking
        assert op.setbit_uint64(42, 64, False) == 42
        return True

    def clear_state_program(self) -> bool:
        return True
