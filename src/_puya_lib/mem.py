from algopy import UInt64, op, subroutine


@subroutine
def new_slot(allocation_slot: UInt64) -> UInt64:
    allocation = op.Scratch.load_bytes(allocation_slot)
    next_slot = op.bitlen(allocation)
    assert next_slot, "no available slots"
    # setbit_bytes takes an index starting with the left most bit of the leftmost byte as index 0
    # so need to invert slot
    bit_to_set = allocation.length * 8 - next_slot
    allocation = op.setbit_bytes(allocation, bit_to_set, 0)
    op.Scratch.store(allocation_slot, allocation)
    return next_slot
