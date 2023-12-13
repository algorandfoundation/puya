from puyapy import (
    Bytes,
    Contract,
    OnCompleteAction,
    Transaction,
    arc4,
    call_application_txn,
    create_application_txn,
    update_application_txn,
)


class MyContract(Contract):
    def approval_program(self) -> bool:
        app = create_application_txn(
            approval_program=b"\x06\x81\x01",
            clear_state_program=Bytes.from_hex("068101"),
            application_args=(Bytes(b"1"), Bytes(b"2")),
            fee=0,
        )

        update_application_txn(
            application_id=app,
            approval_program=b"\x06\x81\x01",
            clear_state_program=Bytes.from_hex("068101"),
            fee=0,
        )

        call_application_txn(
            application_id=app,
            on_completion=OnCompleteAction.DeleteApplication,
        )

        app_arg = Transaction.num_app_args() * 42
        call_application_txn(
            application_id=45678,
            application_args=(
                arc4.arc4_signature("get(uint64)uint64"),
                arc4.UInt64(app_arg).bytes,
            ),
            fee=0,
        )
        return True

    def clear_state_program(self) -> bool:
        return True
