import abc

from algopy import BaseContract, Bytes, LocalState, UInt64, subroutine


class CallCounter(BaseContract, abc.ABC):
    def __init__(self) -> None:
        self.counter = UInt64(0)
        self.name = LocalState(Bytes)

    @subroutine
    def increment_counter(self) -> None:
        self.counter += 1

    @subroutine
    def set_sender_nickname(self, nickname: Bytes) -> None:
        self.name[0] = nickname
