import typing

from algopy import BigUInt, Bytes, Struct, TemplateVar, UInt64, arc4, subroutine
from algopy.arc4 import UInt512


class ATuple(typing.NamedTuple):
    a: UInt64
    b: UInt64


class AStruct(Struct):
    a: UInt64
    b: UInt64


class TemplateVariablesContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def get_bytes(self) -> Bytes:
        return self.receive_value(TemplateVar[Bytes]("SOME_BYTES"))

    @arc4.abimethod()
    def get_big_uint(self) -> UInt512:
        x = TemplateVar[BigUInt]("SOME_BIG_UINT")
        return UInt512(x)

    @arc4.baremethod(allow_actions=["UpdateApplication"])
    def on_update(self) -> None:
        assert TemplateVar[bool]("UPDATABLE")

    @arc4.baremethod(allow_actions=["DeleteApplication"])
    def on_delete(self) -> None:
        assert TemplateVar[UInt64]("DELETABLE")

    @subroutine()
    def receive_value(self, value: Bytes) -> Bytes:
        return value

    @arc4.abimethod
    def get_a_named_tuple(self) -> ATuple:
        return TemplateVar[ATuple]("NAMED_TUPLE")

    @arc4.abimethod
    def get_a_tuple(self) -> tuple[UInt64, UInt64]:
        return TemplateVar[tuple[UInt64, UInt64]]("TUPLE")

    @arc4.abimethod
    def get_a_struct(self) -> AStruct:
        return TemplateVar[AStruct]("STRUCT")
