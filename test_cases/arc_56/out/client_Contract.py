# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class TopLevelStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.String
    shared: algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[8]]]
class SharedStruct(algopy.arc4.Struct):
    foo: algopy.arc4.DynamicBytes
    bar: algopy.arc4.UIntN[typing.Literal[8]]

class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['NoOp', 'OptIn'], create='allow')
    def create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def struct_arg(
        self,
        arg: TopLevelStruct,
        shared: SharedStruct,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(readonly=True)
    def struct_return(
        self,
        arg: TopLevelStruct,
    ) -> algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[8]]]: ...

    @algopy.arc4.abimethod(readonly=True)
    def emits_error(
        self,
        arg: TopLevelStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def emitter(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def conditional_emit(
        self,
        should_emit: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod
    def template_value(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[8]]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String, algopy.arc4.UIntN[typing.Literal[8]]]: ...
