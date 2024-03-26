from algopy import BigUInt, Bytes, TemplateVar, UInt64, arc4
from algopy.arc4 import UInt512


class TemplateVariablesContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def get_bytes(self) -> Bytes:
        return TemplateVar[Bytes]("SOME_BYTES")

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
