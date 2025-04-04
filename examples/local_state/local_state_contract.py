from algopy import (
    Account,
    Bytes,
    Contract,
    LocalState,
    OnCompleteAction,
    String,
    Txn,
    UInt64,
    log,
    subroutine,
)


class LocalStateContract(Contract):
    def __init__(self) -> None:
        self.local = LocalState(Bytes)
        self.local_bool = LocalState(bool)

    def approval_program(self) -> bool:
        if Txn.application_id == 0:
            return True
        if Txn.on_completion not in (OnCompleteAction.NoOp, OnCompleteAction.OptIn):
            return False
        if Txn.num_app_args == 0:
            return False

        method = Txn.application_args(0)
        if Txn.num_app_args == 1:
            if method == b"get_guaranteed_data":
                log(self.get_guaranteed_data(Txn.sender))
            elif method == b"get_data_or_assert":
                log(self.get_data_or_assert(Txn.sender))
            elif method == b"delete_data":
                self.delete_data(Txn.sender)
                log("Deleted")
            else:
                return False
            return True
        elif Txn.num_app_args == 2:
            if method == b"set_data":
                self.set_data(Txn.sender, Txn.application_args(1))
            elif method == b"get_data_with_default":
                log(self.get_data_with_default(Txn.sender, Txn.application_args(1)))
            else:
                return False
            return True
        else:
            return False

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def get_guaranteed_data(self, for_account: Account) -> Bytes:
        result = self.local[for_account]
        # this just tests local state proxy can be passed around
        assert result.length == get_local_state_length(self.local, for_account)
        # tests for dynamic key
        assert local_bytes_exists(for_account, Bytes(b"local"))
        assert read_local_bytes(for_account, String("local")) == result
        return result

    @subroutine
    def get_data_with_default(self, for_account: Account, default: Bytes) -> Bytes:
        # offset contract use arguments without kwarg
        return self.local.get(account=for_account, default=default)

    @subroutine
    def get_data_or_assert(self, for_account: Account) -> Bytes:
        result, exists = self.local.maybe(for_account)
        assert exists, "no data for account"
        return result

    @subroutine
    def set_data(self, for_account: Account, value: Bytes) -> None:
        self.local[for_account] = value

    @subroutine
    def delete_data(self, for_account: Account) -> None:
        del self.local[for_account]


@subroutine
def get_local_state_length(state: LocalState[Bytes], account: Account) -> UInt64:
    return state[account].length


@subroutine
def local_bytes_exists(account: Account, key: Bytes) -> bool:
    return account in LocalState(Bytes, key=key)


@subroutine
def read_local_bytes(account: Account, key: String) -> Bytes:
    return LocalState(Bytes, key=key)[account]
