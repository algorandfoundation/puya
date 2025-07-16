# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Reference(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def noop_with_uint64(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod(allow_actions=['OptIn'])
    def opt_in(
        self,
        uint: algopy.arc4.UIntN[typing.Literal[64]],
        bites: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod(readonly=True, allow_actions=['NoOp', 'OptIn', 'CloseOut', 'UpdateApplication', 'DeleteApplication'], create='allow')
    def all_the_things(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod(readonly=True, allow_actions=['NoOp', 'CloseOut', 'DeleteApplication'])
    def mixed_oca(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod
    def opt_into_asset(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def with_transactions(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        an_int: algopy.arc4.UIntN[typing.Literal[64]],
        pay: algopy.gtxn.PaymentTransaction,
        another_int: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def compare_assets(
        self,
        asset_a: algopy.arc4.UIntN[typing.Literal[64]],
        asset_b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_address(
        self,
    ) -> algopy.arc4.Address: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_asset(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_application(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_an_int(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def method_with_default_args(
        self,
        asset_from_storage: algopy.arc4.UIntN[typing.Literal[64]],
        asset_from_function: algopy.arc4.UIntN[typing.Literal[64]],
        account_from_storage: algopy.arc4.Address,
        account_from_function: algopy.arc4.Address,
        application_from_storage: algopy.arc4.UIntN[typing.Literal[64]],
        application_from_function: algopy.arc4.UIntN[typing.Literal[64]],
        bytes_from_storage: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[3]],
        int_from_storage: algopy.arc4.UIntN[typing.Literal[64]],
        int_from_function: algopy.arc4.UIntN[typing.Literal[64]],
        int_from_const: algopy.arc4.UIntN[typing.Literal[32]],
        str_from_const: algopy.arc4.String,
        int_from_local: algopy.arc4.UIntN[typing.Literal[64]],
        bytes_from_local: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def method_with_15_args(
        self,
        one: algopy.arc4.UIntN[typing.Literal[64]],
        two: algopy.arc4.UIntN[typing.Literal[64]],
        three: algopy.arc4.UIntN[typing.Literal[64]],
        four: algopy.arc4.UIntN[typing.Literal[64]],
        five: algopy.arc4.UIntN[typing.Literal[64]],
        six: algopy.arc4.UIntN[typing.Literal[64]],
        seven: algopy.arc4.UIntN[typing.Literal[64]],
        eight: algopy.arc4.UIntN[typing.Literal[64]],
        nine: algopy.arc4.UIntN[typing.Literal[64]],
        ten: algopy.arc4.UIntN[typing.Literal[64]],
        eleven: algopy.arc4.UIntN[typing.Literal[64]],
        twelve: algopy.arc4.UIntN[typing.Literal[64]],
        thirteen: algopy.arc4.UIntN[typing.Literal[64]],
        fourteen: algopy.arc4.UIntN[typing.Literal[64]],
        fifteen: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes:
        """
        Fifteen args should not encode the last argument as a tuple
        """

    @algopy.arc4.abimethod
    def method_with_more_than_15_args(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        c: algopy.arc4.UIntN[typing.Literal[64]],
        d: algopy.arc4.UIntN[typing.Literal[64]],
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        e: algopy.arc4.UIntN[typing.Literal[64]],
        f: algopy.arc4.UIntN[typing.Literal[64]],
        pay: algopy.gtxn.PaymentTransaction,
        g: algopy.arc4.UIntN[typing.Literal[64]],
        h: algopy.arc4.UIntN[typing.Literal[64]],
        i: algopy.arc4.UIntN[typing.Literal[64]],
        j: algopy.arc4.UIntN[typing.Literal[64]],
        k: algopy.arc4.UIntN[typing.Literal[64]],
        l: algopy.arc4.UIntN[typing.Literal[64]],
        m: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
        o: algopy.arc4.UIntN[typing.Literal[64]],
        p: algopy.arc4.UIntN[typing.Literal[64]],
        q: algopy.arc4.UIntN[typing.Literal[64]],
        r: algopy.arc4.UIntN[typing.Literal[64]],
        s: algopy.arc4.DynamicBytes,
        t: algopy.arc4.DynamicBytes,
        asset2: algopy.arc4.UIntN[typing.Literal[64]],
        pay2: algopy.gtxn.PaymentTransaction,
        u: algopy.arc4.UIntN[typing.Literal[64]],
        v: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]:
        """
        Application calls only support 16 args, and arc4 calls utilise the first arg for the method
        selector. Args beyond this number are packed into a tuple and placed in the 16th slot.
        """

    @algopy.arc4.abimethod
    def hello_with_algopy_string(
        self,
        name: algopy.arc4.String,
    ) -> algopy.arc4.String: ...
