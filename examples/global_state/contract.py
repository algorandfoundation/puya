from algopy import Account, Application, Asset, Bytes, Contract, GlobalState, UInt64, subroutine


class AppStateContract(Contract):
    def __init__(self) -> None:
        self.global_int_full = GlobalState(UInt64(55))
        self.global_int_simplified = UInt64(33)
        self.global_int_no_default = GlobalState(UInt64)

        self.global_bytes_full = GlobalState(Bytes(b"Hello"))
        self.global_bytes_simplified = Bytes(b"Hello")
        self.global_bytes_no_default = GlobalState(Bytes)

        self.global_bool_full = GlobalState(False)
        self.global_bool_simplified = True
        self.global_bool_no_default = GlobalState(bool)

        self.global_asset = GlobalState(Asset)
        self.global_application = GlobalState(Application)
        self.global_account = GlobalState(Account)

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

        # Assert 'is set'
        assert self.global_bool_full
        assert not self.global_bool_no_default

        self.global_bool_no_default.value = True

        # Assert 'value'
        assert not self.global_bool_full.value
        assert self.global_bool_simplified
        assert self.global_bool_no_default.value

        # test the proxy can be passed as an argument
        assert get_global_state_plus_1(self.global_int_no_default) == 45

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def get_global_state_plus_1(state: GlobalState[UInt64]) -> UInt64:
    return state.value + 1
