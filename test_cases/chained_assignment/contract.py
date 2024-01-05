from puyapy import Bytes, Contract, log, subroutine

WAVE = "👋".encode()


class BaseContract(Contract):
    def __init__(self) -> None:
        self.state1 = self.state2 = join_log_and_return(
            right=Bytes(WAVE),
            left=Bytes(b"Hello, world!"),
        )


class ChainedAssignment(BaseContract):
    def __init__(self) -> None:
        super().__init__()

    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def join_log_and_return(*, left: Bytes, right: Bytes) -> Bytes:
    result = left + b" " + right
    log(result)
    return result
