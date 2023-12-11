from puyapy import Contract, UInt64, err, exit


class ContractWithUnreachableCode(Contract):
    def approval_program(self) -> UInt64:
        x = UInt64(0)
        if x:
            return x
        else:
            err()
            return x

    def clear_state_program(self) -> bool:
        exit(1)
        return True
