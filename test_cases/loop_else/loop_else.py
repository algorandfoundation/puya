# ruff: noqa: F403, F405
from algopy import *


class LoopElseContract(Contract):
    def approval_program(self) -> bool:
        test_empty_loop(UInt64(0))

        arg_idx = UInt64(0)
        while arg_idx < Txn.num_app_args:
            for i in urange(10):
                if i == 0:
                    break
                assert False, "unreachable"
            if Txn.application_args(arg_idx) == b"while_secret":
                secret_index = arg_idx
                for account_index in urange(Txn.num_accounts):
                    account = Txn.accounts(account_index)
                    if account == Global.zero_address:
                        break
                else:
                    assert False, "access denied, missing secret account"
                break
            arg_idx += 1
        else:
            assert False, "access denied, missing secret argument"
        log(
            "found secret argument at idx=",
            op.itob(secret_index + 48)[-1],
            " and secret account at idx=",
            op.itob(account_index + 48)[-1],
        )
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_empty_loop(count: UInt64) -> None:
    assert count == 0
    result = UInt64(0)
    for i in reversed(urange(count)):
        if i == 0:
            break
    else:
        result += 1
    assert result == 1
