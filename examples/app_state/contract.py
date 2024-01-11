from puyapy import AppState, Bytes, Contract, UInt64


class AppStateContract(Contract):
    def __init__(self) -> None:
        self.global_int_full = AppState(UInt64(55))
        self.global_int_simplified = UInt64(33)
        self.global_int_no_default = AppState(UInt64)

        self.global_bytes_full = AppState(Bytes(b"Hello"))
        self.global_bytes_simplified = Bytes(b"Hello")
        self.global_bytes_no_default = AppState(Bytes)

    def approval_program(self) -> bool:
        assert self.global_int_simplified == 33
        assert self.global_int_full.exists()
        assert self.global_int_full.get() == 55
        assert not self.global_int_no_default.exists()
        self.global_int_no_default.put(UInt64(44))
        i_value, i_exists = self.global_int_no_default.maybe()
        assert i_exists
        assert i_value == UInt64(44)

        assert self.global_bytes_simplified == Bytes(b"Hello")
        assert self.global_bytes_full.exists()
        assert self.global_bytes_full.get() == Bytes(b"Hello")
        assert not self.global_bytes_no_default.exists()
        self.global_bytes_no_default.put(Bytes(b"World"))
        b_value, b_exists = self.global_bytes_no_default.maybe()
        assert b_exists
        assert b_value == b"World"
        self.global_bytes_no_default.delete()
        b_value, b_exists = self.global_bytes_no_default.maybe()
        assert not b_exists
        return True

    def clear_state_program(self) -> bool:
        return True
