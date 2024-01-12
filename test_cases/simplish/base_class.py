import abc

from puyapy import Bytes, Contract, Local, UInt64, subroutine


class CallCounter(Contract, abc.ABC):
    def __init__(self) -> None:
        self.counter = UInt64(0)
        self.name = Local(Bytes)

    @subroutine
    def increment_counter(self) -> None:
        self.counter += 1

    @subroutine
    def set_sender_nickname(self, nickname: Bytes) -> None:
        self.name[0] = nickname
