from algopy import UInt64, logged_assert, logged_err
from algopy.arc4 import ARC4Contract, abimethod


class LoggedErrorsContract(ARC4Contract):
    @abimethod
    def test_logged_errs(self, arg: UInt64) -> None:
        # code only (default prefix "ERR") -> "ERR:01"
        logged_assert(arg != 1, "01")
        # code + message -> "ERR:02:arg is two"
        logged_assert(arg != 2, "02", error_message="arg is two")
        # code + custom prefix -> "AER:03"
        logged_assert(arg != 3, "03", prefix="AER")
        # unconditional logged_err -> "ERR:04"
        if arg == 4:
            logged_err("04")
