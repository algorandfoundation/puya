from algopy import (
    BigUInt,
    Bytes,
    Contract,
    LocalState,
    OnCompleteAction,
    UInt64,
    op,
)


class Augmented(Contract):
    def __init__(self) -> None:
        self.my_uint = LocalState(UInt64)
        self.my_bytes = LocalState(Bytes)
        self.global_uint = UInt64(0)
        self.global_bytes = Bytes(b"")

    def approval_program(self) -> bool:
        me = op.Txn.sender

        if op.Txn.on_completion == OnCompleteAction.OptIn:
            self.my_uint[me] = UInt64(0)
            self.my_bytes[me] = Bytes(b"")
        if op.Txn.application_id:
            # variable augmented assignment
            n = op.Txn.num_app_args
            bytes_to_add = BigUInt(n).bytes

            # local augmented assignment
            # this works, but need to silence mypy
            self.my_uint[me] += n
            self.my_bytes[me] += bytes_to_add

            # global augmented assignment
            self.global_uint += n
            self.global_bytes += bytes_to_add
        return True

    def clear_state_program(self) -> bool:
        return True
