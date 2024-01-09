from puyapy import Bytes, Contract, ScratchSlot, ScratchSlotRange, UInt64, urange


class MyContract(Contract):
    def __init__(self) -> None:
        self.slot_one = ScratchSlot(1, UInt64)
        self.slot_two = ScratchSlot(UInt64(2), Bytes)
        self.slots_three_to_twenty = ScratchSlotRange(3, 20, UInt64)

    def approval_program(self) -> bool:
        self.slot_one.store(UInt64(5))

        self.slot_two.store(Bytes(b"Hello World"))

        for i in urange(18):
            self.slots_three_to_twenty[i] = i

        assert self.slot_one.load() == UInt64(5)

        assert self.slot_two.load() == b"Hello World"

        assert self.slots_three_to_twenty[5] == UInt64(5)
        return True

    def clear_state_program(self) -> bool:
        return True
