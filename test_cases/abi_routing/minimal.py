from algopy import ARC4Contract, UInt64


class MinimumARC4(ARC4Contract):
    def __init__(self) -> None:
        self.gvalue = UInt64(4)
