import algopy

from test_cases.inheritance.grandparent import GrandParentContract


class ParentContract(GrandParentContract):
    @algopy.subroutine
    def method(self) -> bool:
        algopy.log("ParentContract.method called")
        return super().method()
