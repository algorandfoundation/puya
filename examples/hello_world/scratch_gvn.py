from algopy import Contract, Txn, UInt64, log, op, subroutine


class ScratchGVN(Contract):
    def approval_program(self) -> bool:
        assert scratch_gvn_demo(Txn.num_app_args) == Txn.num_app_args + Txn.num_app_args
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def scratch_gvn_demo(n: UInt64) -> UInt64:
    a = n
    b = n
    while True:
        if not n:
            a = n
            b = n
        log(op.itob(a))
        log(op.itob(b))
        b = a
        a = b
        if not n:
            break
    return a + b
