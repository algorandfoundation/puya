import puyapy


class GrandParentContract(puyapy.Contract):
    def approval_program(self) -> bool:
        return self.method()

    def clear_state_program(self) -> bool:
        return True

    @puyapy.subroutine
    def method(self) -> bool:
        puyapy.log("GrandParentContract.method called")
        return True
