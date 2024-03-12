from puyapy import Contract, urange


class MyOtherContract(Contract, scratch_slots=urange(0, -1, -1)):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
