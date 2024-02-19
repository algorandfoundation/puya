from puyapy import (
    Bytes,
    Contract,
    OnCompleteAction,
    UInt64,
    itxn,
    log,
    op,
    urange,
)

from test_cases.inner_transactions import programs


class MyContract(Contract):
    def clear_state_program(self) -> bool:
        return True

    def approval_program(self) -> bool:
        note = Bytes(b"ABCDE")
        app_params = itxn.ApplicationCall(
            approval_program=programs.ALWAYS_APPROVE,
            clear_state_program=programs.ALWAYS_APPROVE,
            on_completion=OnCompleteAction.DeleteApplication,
            note=b"",
            fee=0,
        )
        for i in urange(4):
            i_note = op.extract(note, 0, i)
            match i:
                case UInt64(1):
                    app_params.set(note=i_note, app_args=(Bytes(b"1"),))
                case UInt64(2):
                    app_params.set(note=i_note, app_args=(Bytes(b"2"), Bytes(b"1")))
                case UInt64(3):
                    app_params.set(
                        note=i_note,
                        app_args=(Bytes(b"3"), Bytes(b"2"), Bytes(b"1")),
                    )
            app_txn = app_params.submit()
            log(app_txn.note)
            log(app_txn.num_app_args)

        return True
