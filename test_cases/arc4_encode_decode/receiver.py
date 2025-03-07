from algopy import ARC4Contract
from algopy.arc4 import Bool, DynamicArray, abimethod


class Receiver(ARC4Contract):
    @abimethod()
    def receive_bools(self, b: DynamicArray[Bool]) -> None:
        assert b.length == 2
        assert b[0]
        assert b[1]
