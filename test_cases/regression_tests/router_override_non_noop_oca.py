import typing

from algopy import ARC4Contract, UInt64, arc4, log


class RouterOverrideNonNoOpOCA(ARC4Contract):
    @typing.override
    def approval_program(self) -> bool:
        return super().approval_program()

    @arc4.abimethod
    def noop_method(self) -> None:
        log("noop")

    @arc4.abimethod
    def another_noop_method(self, val: UInt64) -> None:
        log("another noop", val)

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def update_application(self) -> None:
        log("update")
