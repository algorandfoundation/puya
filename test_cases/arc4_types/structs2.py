from algopy import Contract, arc4, log

from test_cases.arc4_types.structs import Flags


class Arc4StructsFromAnotherModule(Contract):
    def approval_program(self) -> bool:
        flags = Flags(a=arc4.Bool(True), b=arc4.Bool(False), c=arc4.Bool(True), d=arc4.Bool(False))
        log(flags.bytes)

        return True

    def clear_state_program(self) -> bool:
        return True
