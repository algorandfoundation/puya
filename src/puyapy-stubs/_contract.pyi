import abc

from puyapy import UInt64

class Contract(abc.ABC):
    def __init_subclass__(cls, name: str | None = None, **kwargs: object): ...
    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool: ...
    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool: ...
