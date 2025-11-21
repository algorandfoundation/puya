from algopy import BaseContract, urange


class MyOtherContract(BaseContract, scratch_slots=urange(0, -1, -1)):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
