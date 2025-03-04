# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class SharedStruct(algopy.arc4.Struct):
    foo: algopy.arc4.DynamicBytes
    bar: algopy.arc4.UIntN[typing.Literal[8]]

class TopLevelStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.String
    shared: SharedStruct

class EventOnly(algopy.arc4.Struct):
    x: algopy.arc4.UIntN[typing.Literal[64]]
    y: algopy.arc4.UIntN[typing.Literal[64]]

class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Contract docstring
    """
    @algopy.arc4.abimethod(allow_actions=['NoOp', 'OptIn'], create='allow')
    def create(
        self,
    ) -> None:
        """
        Method docstring
        """

    @algopy.arc4.abimethod
    def struct_arg(
        self,
        arg: TopLevelStruct,
        shared: SharedStruct,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]:
        """
        Method docstring2
        """

    @algopy.arc4.abimethod(readonly=True)
    def struct_return(
        self,
        arg: TopLevelStruct,
    ) -> SharedStruct: ...

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

    @algopy.arc4.abimethod
    def with_constant_defaults(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        c: algopy.arc4.DynamicBytes,
        d: EventOnly,
        e: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String],
        f: algopy.arc4.StaticArray[algopy.arc4.String, typing.Literal[2]],
        g: algopy.arc4.DynamicArray[algopy.arc4.String],
        h: algopy.arc4.UIntN[typing.Literal[64]],
        i: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
