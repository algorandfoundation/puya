import typing

from algopy import ARC4Contract, Txn, UInt64, arc4, log, op


class CustomApproval(ARC4Contract):
    def __init__(self) -> None:
        super().__init__()
        assert Txn.application_id == 0, "nonsense assert just to generate an init method"

    @typing.override
    def approval_program(self) -> bool:
        if Txn.num_app_args == 2 and Txn.application_args(1) == op.itob(42):
            log("🎉🎉🎉")
        result = super().approval_program()
        if not result:
            log(
                "this will never be seen unless you're running in simulation mode anyway"
                " so I can say whatever I want here"
            )
        return result

    @arc4.abimethod
    def add_one(self, x: UInt64) -> UInt64:
        return x + 1
