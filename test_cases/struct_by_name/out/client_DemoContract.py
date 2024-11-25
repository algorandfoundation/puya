# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class StructOne(algopy.arc4.Struct):
    x: algopy.arc4.UIntN[typing.Literal[8]]
    y: algopy.arc4.UIntN[typing.Literal[8]]

class StructTwo(algopy.arc4.Struct):
    x: algopy.arc4.UIntN[typing.Literal[8]]
    y: algopy.arc4.UIntN[typing.Literal[8]]

class test_cases_struct_by_name_mod_StructTwo(algopy.arc4.Struct):
    x: algopy.arc4.UIntN[typing.Literal[8]]
    y: algopy.arc4.UIntN[typing.Literal[8]]

class DemoContract(algopy.arc4.ARC4Client, typing.Protocol):
    """

        Verify that even though named tuples with different names but the same structure should be
        considered 'comparable' in the type system, they should be output separately when being
        interpreted as an arc4 Struct in an abi method
    
    """
    @algopy.arc4.abimethod
    def get_one(
        self,
    ) -> StructOne: ...

    @algopy.arc4.abimethod
    def get_two(
        self,
    ) -> StructTwo: ...

    @algopy.arc4.abimethod
    def get_three(
        self,
    ) -> test_cases_struct_by_name_mod_StructTwo: ...

    @algopy.arc4.abimethod
    def compare(
        self,
    ) -> algopy.arc4.Bool: ...
