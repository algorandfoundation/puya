import typing

from puyapy import UInt64

_T = typing.TypeVar("_T")

class ScratchSlot(typing.Generic[_T]):
    def __init__(self, slot_number: int | UInt64, data_type: type[_T], /) -> None: ...
    def load(self) -> _T: ...
    def store(self, val: _T) -> None: ...

class ScratchSlotRange(typing.Generic[_T]):
    def __init__(
        self,
        slot_number_start: int | UInt64,
        slot_number_stop: int | UInt64,
        data_type: type[_T],
        /,
    ) -> None: ...
    def __getitem__(self, item: int | UInt64) -> _T: ...
    def __setitem__(self, key: int | UInt64, value: _T) -> None: ...
