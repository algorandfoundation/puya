from algopy import Contract, UInt64, subroutine, urange


@subroutine(inline=False)
def get_bool() -> bool:
    return True


class MyContract(Contract):
    def approval_program(self) -> UInt64:
        val = UInt64(0)
        for _idx in urange(2):
            if get_bool():
                pass
            elif get_bool():  # noqa: SIM102
                if not get_bool():
                    val += UInt64(123)
        return val

    def clear_state_program(self) -> bool:
        return True
