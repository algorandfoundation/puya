from algopy import (
    ARC4Contract,
    Bytes,
    arc4,
    itxn,
)

LOG_1ST_ARG_AND_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x36\x1A\x00"  # txna ApplicationArgs 0
    b"\xB0"  # log
    b"\x81\x01"  # pushint 1
)
ALWAYS_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x81\x01"  # pushint 1
)


class ArrayAccessContract(ARC4Contract):
    @arc4.abimethod
    def test_branching_array_call(self, maybe: arc4.Bool) -> None:
        if maybe:
            create_app_txn = itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                app_args=(Bytes(b"1"), Bytes(b"2")),
                fee=0,
            ).submit()
        else:
            create_app_txn = itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                app_args=(Bytes(b"3"), Bytes(b"4"), Bytes(b"5")),
                note=b"different param set",
                fee=0,
            ).submit()
        if maybe:
            assert create_app_txn.app_args(0) == b"1", "correct args used 1"
            assert create_app_txn.app_args(1) == b"2", "correct args used 2"
        else:
            assert create_app_txn.app_args(0) == b"3", "correct args used 1"
            assert create_app_txn.app_args(1) == b"4", "correct args used 2"
            assert create_app_txn.app_args(2) == b"5", "correct args used 3"
