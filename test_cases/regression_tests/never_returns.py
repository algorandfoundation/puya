from algopy import ARC4Contract, Txn, UInt64, arc4, log, op, subroutine, urange


class NeverReturnsInlining(ARC4Contract):
    @arc4.abimethod
    def method(self) -> UInt64:
        result = invoke()
        return result


@subroutine(inline=True)
def invoke() -> UInt64:
    op.err()


class NeverReturnsFStack(ARC4Contract):
    @arc4.abimethod
    def method(self) -> UInt64:
        result = invoke_with_fstack()
        return result


@subroutine(inline=True)
def invoke_with_fstack() -> UInt64:
    x = UInt64(1)
    if Txn.num_app_args > 0:
        x = UInt64(2)

    one = UInt64(0)
    for idx in urange(Txn.num_app_args):
        x += idx
        if idx == 0:
            one += 1

    log("you won't see this", one)
    op.err()
