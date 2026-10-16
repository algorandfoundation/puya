from algopy import (
    Box,
    Bytes,
    Contract,
    Txn,
    log,
    op,
)


class ITxnBoxOptBarrier(Contract, avm_version=13):
    def approval_program(self) -> bool:
        arg0 = Txn.application_args(0)
        arg1 = Txn.application_args(1)
        val, exists = op.Box.get(arg0)
        log(val)
        op.ITxnCreate.begin()
        op.ITxnCreate.submit()
        log(Box(Bytes, key=arg0).value)
        op.AppBox.put(Txn.application_id, arg1, arg1)
        log(Box(Bytes, key=arg0).value)
        return True

    def clear_state_program(self) -> bool:
        return True
