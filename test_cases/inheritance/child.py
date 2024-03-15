import puyapy

from test_cases.inheritance.grandparent import GrandParentContract
from test_cases.inheritance.parent import ParentContract


class ChildContract(ParentContract):
    @puyapy.subroutine
    def method(self) -> bool:
        puyapy.log("ChildContract.method called")
        return GrandParentContract.method(self)
