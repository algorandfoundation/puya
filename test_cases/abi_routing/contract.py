import typing

from puyapy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    CreateInnerTransaction,
    Global,
    PaymentTransaction,
    Transaction,
    TransactionType,
    UInt64,
    arc4,
    log,
)

Bytes3: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[3]]


class Reference(ARC4Contract):
    def __init__(self) -> None:
        self.asa = Asset(123)
        self.an_int = UInt64(2)
        self.some_bytes = Bytes3(arc4.Byte(7), arc4.Byte(8), arc4.Byte(9))
        self.creator = Transaction.sender()
        self.app = Application(123)

        assert arc4.arc4_signature("get(uint64,byte[])byte[]"), "has method selector"

    @arc4.abimethod
    def noop_with_uint64(self, a: arc4.UInt64) -> arc4.UInt8:
        result = 1 + a.decode()
        return arc4.UInt8(result)

    @arc4.abimethod(
        allow_actions=[
            "NoOp",
            "OptIn",
            "CloseOut",
            "UpdateApplication",
            "DeleteApplication",
        ],
        name="all_the_things",
        create="allow",
        readonly=True,
    )
    def full_abi_config(self, a: arc4.UInt64) -> arc4.UInt8:
        result = UInt64(1) + a.decode()
        return arc4.UInt8(result)

    @arc4.abimethod(
        allow_actions=[
            "NoOp",
            "CloseOut",
            "DeleteApplication",
        ],
        create=False,
        readonly=True,
    )
    def mixed_oca(self, a: arc4.UInt64) -> arc4.UInt8:
        result = UInt64(1) + a.decode()
        return arc4.UInt8(result)

    @arc4.baremethod(
        allow_actions=[
            "NoOp",
            "OptIn",
            "CloseOut",
            "UpdateApplication",
            "DeleteApplication",
        ],
        create=True,
    )
    def bare_abi_config(self) -> None:
        log(b"Hello World")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Transaction.sender() == Global.creator_address(), "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert not self.asa, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_asset_receiver(Global.current_application_address())
        CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        CreateInnerTransaction.submit()

    @arc4.abimethod
    def with_transactions(
        self, asset: Asset, an_int: arc4.UInt64, pay: PaymentTransaction, another_int: arc4.UInt64
    ) -> None:
        assert self.asa == asset, "is correct asset"
        assert an_int.decode() == 1, "is correct int"
        assert pay.receiver == Global.current_application_address(), "is payment to app"
        assert another_int.decode() == 2, "is correct int"

    @arc4.abimethod
    def compare_assets(self, asset_a: Asset, asset_b: Asset) -> None:
        assert asset_a == asset_b, "asset a == b"

    @arc4.abimethod(readonly=True)
    def get_address(self) -> arc4.Address:
        return arc4.Address.from_bytes(Global.zero_address().bytes)

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
        assert account_from_storage == Global.creator_address(), "wrong account from storage"
        assert account_from_function == Global.zero_address(), "wrong account from function"
        assert application_from_storage == Application(123), "wrong application from storage"
        assert application_from_function == Application(456), "wrong application from function"
        assert bytes_from_storage[0] == arc4.Byte(7), "wrong 0th byte from storage"
        assert bytes_from_storage[1] == arc4.Byte(8), "wrong 1st byte from storage"
        assert bytes_from_storage[2] == arc4.Byte(9), "wrong 2nd byte from storage"
        assert int_from_storage.decode() == 2, "wrong int from storage"
        assert int_from_function.decode() == 3, "wrong int from function"

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
        pay: PaymentTransaction,
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
        s: arc4.UInt64,
        t: arc4.UInt64,
        asset2: Asset,
        pay2: PaymentTransaction,
        u: arc4.UInt64,
        v: arc4.UInt64,
    ) -> arc4.UInt64:
        """
        Application calls only support 16 args, and arc4 calls utilise the first arg for the method
        selector. Args beyond this number are packed into a tuple and placed in the 16th slot.
        """
        assert Transaction.num_app_args() == 16
        assert pay.amount == 100000
        assert pay2.amount == 200000
        assert asset.asset_id
        assert asset2.asset_id
        return arc4.UInt64(
            a.decode()
            + b.decode()
            + c.decode()
            + d
            + e.decode()
            + f.decode()
            + g.decode()
            + h.decode()
            + i.decode()
            + j.decode()
            + k.decode()
            + l.decode()
            + m.decode()
            + n.decode()
            + o.decode()
            + p
            + q.decode()
            + r.decode()
            + s.decode()
            + t.decode()
            + u.decode()
            + v.decode()
        )
