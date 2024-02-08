import abc
from collections.abc import Sequence

from puyapy import UInt64, urange

class Contract(abc.ABC):
    """Base class for an Algorand Smart Contract"""

    def __init_subclass__(
        cls, name: str | None = None, scratch_slots: Sequence[int | urange] = (), **kwargs: object
    ): ...
    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool:
        """Represents the program called for all transactions
        where `OnCompletion` != `ClearState`"""
    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool:
        """Represents the program called when `OnCompletion` == `ClearState`"""
