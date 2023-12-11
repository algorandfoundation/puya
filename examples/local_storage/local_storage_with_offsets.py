from puyapy import (
    Bytes,
    Contract,
    Local,
    OnCompleteAction,
    Transaction,
    UInt64,
    btoi,
    log,
    subroutine,
)


class LocalStorageContract(Contract):
    def __init__(self) -> None:
        self.local = Local(Bytes)

    def approval_program(self) -> bool:
        if Transaction.application_id() == 0:
            return True
        if Transaction.on_completion() not in (OnCompleteAction.NoOp, OnCompleteAction.OptIn):
            return False
        if Transaction.num_app_args() < 1:
            return False

        offset = btoi(Transaction.application_args(0))
        method = Transaction.application_args(1)
        if Transaction.num_app_args() == 2:
            if method == b"get_guaranteed_data":
                log(self.get_guaranteed_data(offset))
            elif method == b"get_data_or_assert":
                log(self.get_data_or_assert(offset))
            elif method == b"delete_data":
                self.delete_data(offset)
                log(b"Deleted")
            else:
                return False
            return True
        elif Transaction.num_app_args() == 3:
            if method == b"set_data":
                self.set_data(offset, Transaction.application_args(2))
            elif method == b"get_data_with_default":
                log(self.get_data_with_default(offset, Transaction.application_args(2)))
            else:
                return False
            return True
        else:
            return False

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def get_guaranteed_data(self, for_account: UInt64) -> Bytes:
        return self.local[for_account]

    @subroutine
    def get_data_with_default(self, for_account: UInt64, default: Bytes) -> Bytes:
        return self.local.get(for_account, default)

    @subroutine
    def get_data_or_assert(self, for_account: UInt64) -> Bytes:
        result, exists = self.local.maybe(for_account)
        assert exists, "no data for account"
        return result

    @subroutine
    def set_data(self, for_account: UInt64, value: Bytes) -> None:
        self.local[for_account] = value

    @subroutine
    def delete_data(self, for_account: UInt64) -> None:
        del self.local[for_account]
