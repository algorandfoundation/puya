from puyapy import Contract, UInt64, log, op


class MyContract(Contract):
    def approval_program(self) -> bool:
        do_log = False
        match op.Txn.num_app_args:
            case UInt64(1):
                do_log = True
            case UInt64(3):
                do_log = True
        if do_log:
            log(op.itob(op.Txn.num_app_args))
        return True

    def clear_state_program(self) -> bool:
        return True
