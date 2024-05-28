from algopy import (
    ARC4Contract,
    Bytes,
    OnCompleteAction,
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


class FieldTupleContract(ARC4Contract):
    @arc4.abimethod
    def test_assign_tuple(self) -> None:
        create_txns = (
            itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                on_completion=OnCompleteAction.DeleteApplication,
                app_args=(Bytes(b"1a"), Bytes(b"2a")),
            ),
            itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                on_completion=OnCompleteAction.DeleteApplication,
                app_args=(Bytes(b"3a"), Bytes(b"4a"), Bytes(b"5a")),
                note=b"different param set",
            ),
        )
        txn_1, txn_2 = itxn.submit_txns(create_txns[0], create_txns[1])

        assert txn_1.app_args(0) == b"1a"
        assert txn_1.app_args(1) == b"2a"
        assert txn_2.app_args(0) == b"3a"
        assert txn_2.app_args(1) == b"4a"
        assert txn_2.app_args(2) == b"5a"

        create_txns[0].set(app_args=(Bytes(b"1b"), Bytes(b"2b")))
        create_txns[1].set(app_args=(Bytes(b"3b"), Bytes(b"4b"), Bytes(b"5b")))

        txn_1, txn_2 = itxn.submit_txns(create_txns[1], create_txns[0])

        assert txn_2.app_args(0) == b"1b"
        assert txn_2.app_args(1) == b"2b"
        assert txn_1.app_args(0) == b"3b"
        assert txn_1.app_args(1) == b"4b"
        assert txn_1.app_args(2) == b"5b"

        create_txns[0].set(app_args=(Bytes(b"1c"), Bytes(b"2c")))
        create_txns[1].set(app_args=(Bytes(b"3c"), Bytes(b"4c"), Bytes(b"5c")))

        txn_tuple = itxn.submit_txns(create_txns[0], create_txns[1])

        assert txn_tuple[0].app_args(0) == b"1c"
        assert txn_tuple[0].app_args(1) == b"2c"
        assert txn_tuple[1].app_args(0) == b"3c"
        assert txn_tuple[1].app_args(1) == b"4c"
        assert txn_tuple[1].app_args(2) == b"5c"

    @arc4.abimethod
    def test_assign_tuple_mixed(self) -> None:
        tuple_with_txn_fields = (
            itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                on_completion=OnCompleteAction.DeleteApplication,
                app_args=(Bytes(b"1a"), Bytes(b"2a")),
            ),
            Bytes(b"some other value"),
        )
        result_with_txn = tuple_with_txn_fields[0].submit(), tuple_with_txn_fields[1]

        assert result_with_txn[0].app_args(0) == b"1a"
        assert result_with_txn[0].app_args(1) == b"2a"
        assert result_with_txn[1] == b"some other value"
