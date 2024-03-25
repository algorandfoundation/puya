from puyapy import Account, Bytes, Contract, Global, Txn, UInt64, subroutine


class Throwaway(Contract):
    def approval_program(self) -> bool:
        tup = get_tuple()
        args, sender, _ = tup
        _, _, approval = tup
        assert sender == Global.creator_address
        assert args == 0
        assert approval
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def get_tuple() -> tuple[UInt64, Account, Bytes]:
    return Txn.num_app_args, Txn.sender, Txn.approval_program
