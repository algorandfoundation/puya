from puyapy import ARC4Contract, Txn
from puyapy.arc4 import Bool, DynamicArray, String, Tuple, UInt256, abimethod


class Contract(ARC4Contract):
    @abimethod
    def verify(self, values: DynamicArray[UInt256]) -> Tuple[Bool, String]:
        val1 = Bool(
            bool(Txn.num_app_args)
        )  # use a non constant value so the repeated expression is not simplified
        if values.length != 2:
            return Tuple((val1, String("")))
        return Tuple((val1, String("")))
