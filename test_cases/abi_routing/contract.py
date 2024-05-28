import typing

from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Bytes,
    OnCompleteAction,
    String,
    TransactionType,
    UInt64,
    arc4,
    gtxn,
    log,
    op,
)

Bytes3: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[3]]


class Reference(ARC4Contract):
    def __init__(self) -> None:
        self.asa = Asset(123)
        self.an_int = UInt64(2)
        self.some_bytes = Bytes3(arc4.Byte(7), arc4.Byte(8), arc4.Byte(9))
        self.creator = op.Txn.sender
        self.app = Application(123)

        assert arc4.arc4_signature("get(uint64,byte[])byte[]"), "has method selector"

    @arc4.abimethod
    def noop_with_uint64(self, a: arc4.UInt64) -> arc4.UInt8:
        result = 1 + a.native
        return arc4.UInt8(result)

    @arc4.abimethod(
        allow_actions=[
            "NoOp",
            OnCompleteAction.OptIn,
            "CloseOut",
            OnCompleteAction.UpdateApplication,
            OnCompleteAction.DeleteApplication,
        ],
        name="all_the_things",
        create="allow",
        readonly=True,
    )
    def full_abi_config(self, a: arc4.UInt64) -> arc4.UInt8:
        result = UInt64(1) + a.native
        return arc4.UInt8(result)

    @arc4.abimethod(
        allow_actions=[
            "NoOp",
            "CloseOut",
            "DeleteApplication",
        ],
        create="disallow",
        readonly=True,
    )
    def mixed_oca(self, a: arc4.UInt64) -> arc4.UInt8:
        result = UInt64(1) + a.native
        return arc4.UInt8(result)

    @arc4.baremethod(
        allow_actions=[
            "NoOp",
            "OptIn",
            "CloseOut",
            "UpdateApplication",
            "DeleteApplication",
        ],
        create="require",
    )
    def bare_abi_config(self) -> None:
        log("Hello World")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert op.Txn.sender == op.Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert not self.asa, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        op.ITxnCreate.begin()
        op.ITxnCreate.set_type_enum(TransactionType.AssetTransfer)
        op.ITxnCreate.set_fee(UInt64(0))  # cover fee with outer txn
        op.ITxnCreate.set_asset_receiver(op.Global.current_application_address)
        op.ITxnCreate.set_xfer_asset(asset)
        op.ITxnCreate.submit()

    @arc4.abimethod
    def with_transactions(
        self,
        asset: Asset,
        an_int: arc4.UInt64,
        pay: gtxn.PaymentTransaction,
        another_int: arc4.UInt64,
    ) -> None:
        assert self.asa == asset, "is correct asset"
        assert an_int.native == 1, "is correct int"
        assert pay.receiver == op.Global.current_application_address, "is payment to app"
        assert another_int.native == 2, "is correct int"

    @arc4.abimethod
    def compare_assets(self, asset_a: Asset, asset_b: Asset) -> None:
        assert asset_a == asset_b, "asset a == b"

    @arc4.abimethod(readonly=True)
    def get_address(self) -> arc4.Address:
        return arc4.Address()

    @arc4.abimethod(readonly=True)
    def get_asset(self) -> arc4.UInt64:
        return arc4.UInt64(456)

    @arc4.abimethod(readonly=True, name="get_application")
    def get_app(self) -> arc4.UInt64:
        return arc4.UInt64(456)

    @arc4.abimethod(readonly=True, name="get_an_int")
    def get_a_int(self) -> arc4.UInt64:
        return arc4.UInt64(3)

    @arc4.abimethod(
        default_args={
            "asset_from_storage": "asa",
            "asset_from_function": get_asset,
            "account_from_storage": "creator",
            "account_from_function": "get_address",
            "application_from_storage": "app",
            "application_from_function": get_app,
            "bytes_from_storage": "some_bytes",
            "int_from_storage": "an_int",
            "int_from_function": "get_a_int",
        }
    )
    def method_with_default_args(
        self,
        asset_from_storage: Asset,
        asset_from_function: Asset,
        account_from_storage: Account,
        account_from_function: Account,
        application_from_storage: Application,
        application_from_function: Application,
        bytes_from_storage: Bytes3,
        int_from_storage: arc4.UInt64,
        int_from_function: arc4.UInt64,
    ) -> None:
        assert asset_from_storage == Asset(123), "wrong asset from storage"
        assert asset_from_function == Asset(456), "wrong asset from function"
        assert account_from_storage == op.Global.creator_address, "wrong account from storage"
        assert account_from_function == op.Global.zero_address, "wrong account from function"
        assert application_from_storage == Application(123), "wrong application from storage"
        assert application_from_function == Application(456), "wrong application from function"
        assert bytes_from_storage[0] == arc4.Byte(7), "wrong 0th byte from storage"
        assert bytes_from_storage[1] == arc4.Byte(8), "wrong 1st byte from storage"
        assert bytes_from_storage[2] == arc4.Byte(9), "wrong 2nd byte from storage"
        assert int_from_storage.native == 2, "wrong int from storage"
        assert int_from_function.native == 3, "wrong int from function"

    @arc4.abimethod
    def method_with_more_than_15_args(
        self,
        a: arc4.UInt64,
        b: arc4.UInt64,
        c: arc4.UInt64,
        d: UInt64,
        asset: Asset,
        e: arc4.UInt64,
        f: arc4.UInt64,
        pay: gtxn.PaymentTransaction,
        g: arc4.UInt64,
        h: arc4.UInt64,
        i: arc4.UInt64,
        j: arc4.UInt64,
        k: arc4.UInt64,
        # ruff: noqa: E741
        l: arc4.UInt64,
        m: arc4.UInt64,
        n: arc4.UInt64,
        o: arc4.UInt64,
        p: UInt64,
        q: arc4.UInt64,
        r: arc4.UInt64,
        s: Bytes,
        t: Bytes,
        asset2: Asset,
        pay2: gtxn.PaymentTransaction,
        u: arc4.UInt64,
        v: arc4.UInt64,
    ) -> arc4.UInt64:
        """
        Application calls only support 16 args, and arc4 calls utilise the first arg for the method
        selector. Args beyond this number are packed into a tuple and placed in the 16th slot.
        """
        assert op.Txn.num_app_args == 16
        assert pay.amount == 100000
        assert pay2.amount == 200000
        assert asset.id
        assert asset2.id

        log(s + t)

        return arc4.UInt64(
            a.native
            + b.native
            + c.native
            + d
            + e.native
            + f.native
            + g.native
            + h.native
            + i.native
            + j.native
            + k.native
            + l.native
            + m.native
            + n.native
            + o.native
            + p
            + q.native
            + r.native
            + u.native
            + v.native
        )

    @arc4.abimethod
    def hello_with_algopy_string(self, name: String) -> String:
        return "Hello " + name + "!"
