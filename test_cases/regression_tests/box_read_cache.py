from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class BoxReadCache(ARC4Contract):
    def __init__(self) -> None:
        self.b = Box(Bytes, key=b"k")

    @arc4.abimethod
    def repro(self) -> arc4.Tuple[arc4.Bool, arc4.Bool, arc4.UInt64, arc4.UInt64]:
        # Box does not exist initially, so we should have empty v1 and False
        v1, exists1 = self.b.maybe()
        self.b.create(size=UInt64(16))

        # we should see: len(v2) = 16, exists2 = True
        v2, exists2 = self.b.maybe()

        return arc4.Tuple[arc4.Bool, arc4.Bool, arc4.UInt64, arc4.UInt64](
            (
                arc4.Bool(exists1),
                arc4.Bool(exists2),
                arc4.UInt64(v1.length),
                arc4.UInt64(v2.length),
            )
        )
