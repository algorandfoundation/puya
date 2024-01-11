import abc

from puyapy import AppAccountState, Bytes, Contract, UInt64, subroutine


class CallCounter(Contract, abc.ABC):
    def __init__(self) -> None:
        self.counter = UInt64(0)
        self.name = AppAccountState(Bytes)

    @subroutine
    def increment_counter(self) -> None:
        self.counter += 1

    @subroutine
    def set_sender_nickname(self, nickname: Bytes) -> None:
        self.name[0] = nickname
