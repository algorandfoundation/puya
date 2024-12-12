from algopy import TemplateVar, UInt64, op, subroutine


@subroutine
def new_slot() -> UInt64:
    allocation = op.Scratch.load_bytes(TemplateVar[UInt64]("_PUYA_ALLOCATION_SLOT"))
    next_slot = op.bitlen(allocation)
    # setbit_bytes takes an index starting with the left most bit of the leftmost byte as index 0
    # so need to invert slot
    bit_to_set = 256 - next_slot
    allocation = op.setbit_bytes(allocation, bit_to_set, 0)
    op.Scratch.store(TemplateVar[UInt64]("_PUYA_ALLOCATION_SLOT"), allocation)
    return next_slot
