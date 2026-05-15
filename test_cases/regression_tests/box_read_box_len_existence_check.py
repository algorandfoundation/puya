from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class BoxReadBoxLenExistenceCheck(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(Bytes, key=b"k")

    @arc4.abimethod
    def len_via_value(self) -> UInt64:
        # this should fail as the box does not exist
        v = self.box.value
        return v.length
