from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class AppCall(ARC4Contract):
    @arc4.abimethod()
    def some_value(self) -> UInt64:
        return Global.group_size * (Txn.group_index + 1)
