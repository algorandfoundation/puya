from algopy import UInt64, logged_assert, logged_err
from algopy.arc4 import ARC4Contract, abimethod


class LoggedErrorsContract(ARC4Contract):
    @abimethod
    def test_logged_errs(self, arg: UInt64) -> None:
        # "ERR:01"
        logged_assert(arg != 1, "01")
        # "ERR:arg02:arg is two"
        logged_assert(arg != 2, "arg02", error_message="arg is two")
        # "AER:arg03"
        logged_assert(arg != 3, "arg03", prefix="AER")
        # "AER:arg04:arg is 4"
        logged_assert(arg != 4, "arg04", error_message="arg is 4", prefix="AER")

        # "ERR:arg05"
        if arg == 5:
            logged_err("arg05")
        # "ERR:arg06:arg was 6"
        if arg == 6:
            logged_err("06", error_message="arg was 6")
        # "AER:arg07"
        if arg == 7:
            logged_err("arg07", prefix="AER")
        # "AER:arg08:arg is seven (08)"
        if arg == 8:
            logged_err("arg08", error_message="arg is eight (08)", prefix="AER")

        # logs "ERR:arg09:arg is nine", with verbose sourceInfo comment
        logged_assert(
            arg != 9,
            "arg09",
            error_message="arg is nine",
            desc="arg should not be nine because...[insert long-winded explanation about the "
            "rather tragic implications of the number 9]",
        )
        # logs "ERR:arg10", with verbose sourceInfo comment
        if arg == 10:
            logged_err(
                "arg10",
                desc="arg should not be ten because...[insert a long-winded explanation about "
                "the somewhat less tragic but still not quite OK implications of using the "
                "number 10]",
            )
