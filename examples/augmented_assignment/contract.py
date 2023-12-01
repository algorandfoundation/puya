from algopy import BigUInt, Bytes, Contract, Local, OnCompleteAction, Transaction, UInt64


class Augmented(Contract):
    def __init__(self) -> None:
        self.my_uint = Local(UInt64)
        self.my_bytes = Local(Bytes)
        self.global_uint = UInt64(0)
        self.global_bytes = Bytes(b"")

    def approval_program(self) -> bool:
        me = Transaction.sender()

        if Transaction.on_completion() == OnCompleteAction.OptIn:
            self.my_uint[me] = UInt64(0)
            self.my_bytes[me] = Bytes(b"")
        if Transaction.application_id() > 0:
            # variable augmented assignment
            n = Transaction.num_app_args()
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
