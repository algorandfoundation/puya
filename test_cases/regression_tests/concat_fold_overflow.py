from algopy import Bytes, Contract, Txn, log


class ConcatFoldOverflow(Contract):
    def approval_program(self) -> bool:
        log(Bytes(b"\x00" * 3000) + Bytes(b"\x00" * 2000))
        log(Txn.sender.bytes + Bytes(b"\x00" * 3000) + Bytes(b"\x00" * 2000))
        log(Bytes(b"\x00" * 3000) + Bytes(b"\x00" * 2000) + Txn.sender.bytes)
        return True

    def clear_state_program(self) -> bool:
        return True
