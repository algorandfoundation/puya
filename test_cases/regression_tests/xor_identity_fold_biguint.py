from algopy import BigUInt, Contract, op, subroutine


class XorIdentityFoldBigUInt(Contract):
    def approval_program(self) -> bool:
        x = BigUInt(2**32 - 1)  # 4 bytes: 0xffffffff
        result = self_xor(x)
        # `x ^ x` on the AVM produces a zero-filled byte array the same
        # length as the inputs — NOT a BigUInt(0) (which has zero length).
        assert result.bytes == op.bzero(x.bytes.length)
        assert result.bytes.length == x.bytes.length
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def self_xor(x: BigUInt) -> BigUInt:
    # must not be folded to BigUInt(0) — the AVM b^ op preserves input length
    return x ^ x
