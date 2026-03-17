import typing

from algopy import ARC4Contract, FixedArray, Global, String, Struct, UInt64, public


class Data(Struct):
    timestamp: UInt64
    value: String


class FixedArrayDynamicElements(ARC4Contract):
    def __init__(self) -> None:
        default = Data(timestamp=Global.latest_timestamp, value=String())
        self.data = FixedArray[Data, typing.Literal[3]].full(default)

    @public
    def write_at_index(self, index: UInt64, value: String) -> None:
        self.data[index] = Data(timestamp=Global.latest_timestamp, value=value)

    @public
    def read_at_index(self, index: UInt64) -> Data:
        return self.data[index]
