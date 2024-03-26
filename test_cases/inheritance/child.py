import algopy

from test_cases.inheritance.grandparent import GrandParentContract
from test_cases.inheritance.parent import ParentContract


class ChildContract(ParentContract):
    @algopy.subroutine
    def method(self) -> bool:
        algopy.log("ChildContract.method called")
        return GrandParentContract.method(self)
