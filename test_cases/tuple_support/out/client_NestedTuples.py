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

class ParentWithList(algopy.arc4.Struct):
    parent: Parent
    children: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes, algopy.arc4.String]]

class SimpleTup(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class TupleWithMutable(algopy.arc4.Struct):
    arr: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]
    child: Child

class NestedTuples(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def store_tuple(
        self,
        pwl: ParentWithList,
    ) -> None: ...

    @algopy.arc4.abimethod
    def load_tuple(
        self,
    ) -> ParentWithList: ...

    @algopy.arc4.abimethod
    def store_tuple_in_box(
        self,
        key: SimpleTup,
    ) -> None: ...

    @algopy.arc4.abimethod
    def is_tuple_in_box(
        self,
        key: SimpleTup,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def load_tuple_from_box(
        self,
        key: SimpleTup,
    ) -> SimpleTup: ...

    @algopy.arc4.abimethod
    def maybe_load_tuple_from_box(
        self,
        key: SimpleTup,
    ) -> algopy.arc4.Tuple[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def load_tuple_from_box_or_default(
        self,
        key: SimpleTup,
    ) -> SimpleTup: ...

    @algopy.arc4.abimethod
    def load_tuple_from_local_state_or_default(
        self,
        key: algopy.arc4.String,
    ) -> SimpleTup: ...

    @algopy.arc4.abimethod
    def mutate_local_tuple(
        self,
    ) -> TupleWithMutable: ...

    @algopy.arc4.abimethod
    def mutate_tuple_in_storage_currently_supported_method(
        self,
    ) -> None: ...

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
