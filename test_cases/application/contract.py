from puyapy import (
    Application,
    Bytes,
    Contract,
    LocalState,
    UInt64,
    op,
    subroutine,
)


class Reference(Contract):
    def __init__(self) -> None:
        self.int_1 = UInt64(0)
        self.bytes_1 = Bytes(b"")
        self.bytes_2 = Bytes(b"")
        self.int_l1 = LocalState(UInt64)
        self.int_l2 = LocalState(UInt64)
        self.int_l3 = LocalState(UInt64)
        self.bytes_l1 = LocalState(Bytes)
        self.bytes_l2 = LocalState(Bytes)
        self.bytes_l3 = LocalState(Bytes)
        self.bytes_l4 = LocalState(Bytes)

    def approval_program(self) -> bool:
        if op.Txn.num_app_args == 1:
            if op.Txn.application_args(0) == b"validate":
                self.validate_asset(op.Global.current_application_id)
            else:
                assert False, "Expected validate"
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def validate_asset(self, app: Application) -> None:
        assert app.creator == op.Global.creator_address, "expected creator"
        assert app.global_num_uint == 1, "expected global_num_uint"
        assert app.global_num_byte_slice == 2, "expected global_num_byte_slice"
        assert app.local_num_uint == 3, "expected local_num_uint"
        assert app.local_num_byte_slice == 4, "expected local_num_byte_slice"
        assert app.approval_program, "expected approval_program"
        assert app.clear_state_program, "expected clear_state_program"
        assert app == op.Global.current_application_id, "expected current_application_id"
        assert (
            app.address == op.Global.current_application_address
        ), "expected current_application_address"
