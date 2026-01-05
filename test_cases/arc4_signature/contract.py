import typing

from algopy import Account, Application, ARC4Contract, Asset, FixedBytes, UInt64, gtxn
from algopy.arc4 import (
    Address,
    Bool,
    DynamicArray,
    StaticArray,
    UFixedNxM,
    UInt32,
    abimethod,
    arc4_signature,
)


class ContractOne(ARC4Contract):
    @abimethod
    def test(self) -> None:
        assert arc4_signature(ContractTwo.some_method) == arc4_signature(
            "renamed_some_method()void"
        )

        assert arc4_signature(ContractTwo.test_tuple) == arc4_signature(
            "test_tuple((uint64,ufixed64x10,asset[3],uint32[],bool,address,byte[16]))(uint64,ufixed64x10,uint64[3],uint32[],bool,address,byte[16])"
        )

    @abimethod
    def some_method(self) -> UInt64:
        return UInt64(123)

    @abimethod
    def test_reference_types(self) -> None:
        assert arc4_signature(ContractTwo.reference_types_index) == arc4_signature(
            "reference_types_index(pay,asset,account,application,appl)void"
        )
        assert arc4_signature(ContractTwo.reference_types_value) == arc4_signature(
            "reference_types_value(pay,uint64,address,uint64,appl)void"
        )


class ContractTwo(ARC4Contract):
    @abimethod(name="renamed_some_method")
    def some_method(self) -> None:
        pass

    @abimethod
    def test(self) -> bool:
        return arc4_signature(ContractOne.some_method) == arc4_signature("some_method()uint64")

    @abimethod(resource_encoding="index")
    def reference_types_index(
        self,
        pay: gtxn.PaymentTransaction,
        asset: Asset,
        account: Account,
        app: Application,
        app_txn: gtxn.ApplicationCallTransaction,
    ) -> None:
        pass

    @abimethod(resource_encoding="value")
    def reference_types_value(
        self,
        pay: gtxn.PaymentTransaction,
        asset: Asset,
        account: Account,
        app: Application,
        app_txn: gtxn.ApplicationCallTransaction,
    ) -> None:
        pass

    @abimethod(resource_encoding="index")
    def test_tuple(
        self,
        val: tuple[
            UInt64,
            UFixedNxM[typing.Literal[64], typing.Literal[10]],
            StaticArray[Asset, typing.Literal[3]],
            DynamicArray[UInt32],
            Bool,
            Address,
            FixedBytes[typing.Literal[16]],
        ],
    ) -> tuple[
        UInt64,
        UFixedNxM[typing.Literal[64], typing.Literal[10]],
        StaticArray[Asset, typing.Literal[3]],
        DynamicArray[UInt32],
        Bool,
        Address,
        FixedBytes[typing.Literal[16]],
    ]:
        return val
