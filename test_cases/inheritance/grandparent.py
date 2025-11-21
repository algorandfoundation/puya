import algopy


class GreatGrandParentContract(algopy.BaseContract):
    def approval_program(self) -> bool:
        return self.method()

    def clear_state_program(self) -> bool:
        return True

    @algopy.subroutine
    def method(self) -> bool:
        algopy.log("GrandParentContract.method called")
        return True


class GrandParentContract(GreatGrandParentContract):
    pass
