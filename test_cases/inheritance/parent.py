import puyapy

from test_cases.inheritance.grandparent import GrandParentContract


class ParentContract(GrandParentContract):
    @puyapy.subroutine
    def method(self) -> bool:
        puyapy.log("ParentContract.method called")
        return super().method()
