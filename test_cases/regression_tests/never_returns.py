from algopy import ARC4Contract, UInt64, arc4, op, subroutine


class NeverReturnsInlining(ARC4Contract):
    @arc4.abimethod
    def method(self) -> UInt64:
        result = invoke()
        return result


@subroutine(inline=True)
def invoke() -> UInt64:
    op.err()
