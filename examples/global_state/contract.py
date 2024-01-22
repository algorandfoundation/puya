from puyapy import Bytes, Contract, GlobalState, UInt64


class AppStateContract(Contract):
    def __init__(self) -> None:
        self.global_int_full = GlobalState(UInt64(55))
        self.global_int_simplified = UInt64(33)
        self.global_int_no_default = GlobalState(UInt64)

        self.global_bytes_full = GlobalState(Bytes(b"Hello"))
        self.global_bytes_simplified = Bytes(b"Hello")
        self.global_bytes_no_default = GlobalState(Bytes)

    def approval_program(self) -> bool:
        assert self.global_int_simplified == 33
        assert self.global_int_full
        assert self.global_int_full.value == 55
        assert not self.global_int_no_default
        self.global_int_no_default.value = UInt64(44)
        i_value, i_exists = self.global_int_no_default.maybe()
        assert i_exists
        assert i_value == 44

        assert self.global_bytes_simplified == b"Hello"
        assert self.global_bytes_full
        assert self.global_bytes_full.value == b"Hello"
        assert self.global_bytes_full.get(Bytes(b"default")) == b"Hello"
        assert not self.global_bytes_no_default
        self.global_bytes_no_default.value = Bytes(b"World")
        b_value, b_exists = self.global_bytes_no_default.maybe()
        assert b_exists
        assert b_value == b"World"
        del self.global_bytes_no_default.value
        b_value, b_exists = self.global_bytes_no_default.maybe()
        assert not b_exists

        assert self.global_bytes_no_default.get(Bytes(b"default")) == b"default"
        return True

    def clear_state_program(self) -> bool:
        return True
