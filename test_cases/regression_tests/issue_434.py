from algopy import ARC4Contract, Global, Txn, UInt64, arc4, op


class Issue434(ARC4Contract):
    # ref: https://github.com/algorandfoundation/puya/issues/434
    @arc4.abimethod
    def method(self, c: UInt64) -> None:
        while Global.opcode_budget() > 350:
            assert op.sha3_256(Txn.sender.bytes) != Txn.sender.bytes

        if c > 0:
            x = c + 2
        else:
            x = c + 2

        assert x - 2 == c
