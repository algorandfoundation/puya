import typing

from algopy import ARC4Contract, arc4

from test_cases.struct_by_name.mod import StructTwo as StructThree


class StructOne(typing.NamedTuple):
    x: arc4.UInt8
    y: arc4.UInt8


class StructTwo(typing.NamedTuple):
    x: arc4.UInt8
    y: arc4.UInt8


class DemoContract(ARC4Contract):
    """
    Verify that even though named tuples with different names but the same structure should be
    considered 'comparable' in the type system, they should be output separately when being
    interpreted as an arc4 Struct in an abi method
    """

    @arc4.abimethod()
    def get_one(self) -> StructOne:
        return StructOne(
            x=arc4.UInt8(1),
            y=arc4.UInt8(1),
        )

    @arc4.abimethod()
    def get_two(self) -> StructTwo:
        return StructTwo(
            x=arc4.UInt8(1),
            y=arc4.UInt8(1),
        )

    @arc4.abimethod()
    def get_three(self) -> StructThree:
        return StructThree(
            x=arc4.UInt8(1),
            y=arc4.UInt8(1),
        )

    @arc4.abimethod()
    def compare(self) -> bool:
        return self.get_one() == self.get_two() and self.get_two() == self.get_three()
