from algopy import BigUInt, Bytes, Contract, log, op


class MyContract(Contract):
    def approval_program(self) -> bool:
        log(0)
        log(b"1")
        log("2")
        log(op.Txn.num_app_args + 3)
        log(Bytes(b"4") if op.Txn.num_app_args else Bytes())
        log(
            b"5",
            6,
            op.Txn.num_app_args + 7,
            BigUInt(8),
            Bytes(b"9") if op.Txn.num_app_args else Bytes(),
        )
        log(
            b"5",
            6,
            op.Txn.num_app_args + 7,
            BigUInt(8),
            Bytes(b"9") if op.Txn.num_app_args else Bytes(),
            sep=b"_",
        )
        log(
            b"5",
            6,
            op.Txn.num_app_args + 7,
            BigUInt(8),
            Bytes(b"9") if op.Txn.num_app_args else Bytes(),
            sep="_",
        )
        return True

    def clear_state_program(self) -> bool:
        return True
