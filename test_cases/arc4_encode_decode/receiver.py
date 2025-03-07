from algopy import ARC4Contract
from algopy.arc4 import Bool, DynamicArray, abimethod


class Receiver(ARC4Contract):
    @abimethod()
    def receive_bools(self, b: DynamicArray[Bool]) -> None:
        assert b.length == 2, "expected 2 bools"
        assert b[0], "expected first bool to be true"
        assert b[1], "expected second bool to be true"

    @abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        pass
