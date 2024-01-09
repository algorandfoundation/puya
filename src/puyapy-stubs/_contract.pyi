import abc
from typing import Union, Sequence

from puyapy import UInt64, urange

class Contract(abc.ABC):
    def __init_subclass__(
        cls,
        name: str | None = None,
        scratch_slots: Sequence[Union[int, urange]] = (),
        **kwargs: object
    ): ...
    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool: ...
    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool: ...
