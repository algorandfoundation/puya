# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class Child(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.DynamicBytes
    c: algopy.arc4.String

class Parent(algopy.arc4.Struct):
    foo: algopy.arc4.UIntN[typing.Literal[64]]
    foo_arc: algopy.arc4.UIntN[typing.Literal[64]]
    child: Child

class NestedTuples(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def run_tests(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def nested_tuple_params(
        self,
        args: algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]]]]],
    ) -> algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.UIntN[typing.Literal[64]]]]: ...

    @algopy.arc4.abimethod
    def named_tuple(
        self,
        args: Child,
    ) -> Child: ...

    @algopy.arc4.abimethod
    def nested_named_tuple_params(
        self,
        args: Parent,
    ) -> Parent: ...
