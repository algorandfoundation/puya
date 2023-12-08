from algopy import ARC4Contract, arc4


class Arc4DynamicStringArrayContract(ARC4Contract):
    @arc4.abimethod
    def xyz(self) -> arc4.DynamicArray[arc4.String]:
        return arc4.DynamicArray(
            arc4.String("X"),
            arc4.String("Y"),
            arc4.String("Z"),
        )

    @arc4.abimethod
    def xyz_raw(self) -> arc4.DynamicArray[arc4.String]:
        raw = arc4.DynamicArray(
            arc4.DynamicArray(arc4.Byte(88)),
            arc4.DynamicArray(arc4.Byte(89)),
            arc4.DynamicArray(arc4.Byte(90)),
        )
        return arc4.DynamicArray[arc4.String].from_bytes(raw.bytes)
