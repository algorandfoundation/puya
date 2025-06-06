from algopy import Array, Contract, Txn, UInt64, ensure_budget, op, subroutine


class SlotAllocationInlining(Contract):
    def approval_program(self) -> bool:
        ensure_budget(800)
        do_something_with_array()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def do_something_with_array() -> None:
    # create pseudo random array from sender address
    arr = Array[UInt64]()
    append_to_array(arr)
    assert arr.length == 32, "expected array of length 32"


@subroutine(inline=False)
def append_to_array(arr: Array[UInt64]) -> None:
    for b in Txn.sender.bytes:
        arr.append(op.btoi(b))
