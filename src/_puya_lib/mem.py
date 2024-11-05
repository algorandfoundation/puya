from algopy import UInt64, op, subroutine


@subroutine
def new_slot(allocation_slot: UInt64) -> UInt64:
    allocation = op.Scratch.load_bytes(allocation_slot)
    next_slot = op.bitlen(allocation)
    assert next_slot, "no available slots"
    allocation = op.setbit_bytes(allocation, next_slot, 0)
    op.Scratch.store(allocation_slot, allocation)
    return next_slot
