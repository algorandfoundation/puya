from algopy import (
    Application,
    ARC4Contract,
    Array,
    Global,
    UInt64,
    gtxn,
    itxn,
    public,
)
from algopy._unsigned_builtins import urange
from algopy.arc4 import Address, arc4_signature


class DynamicITxnGroup(ARC4Contract):
    @public
    def test_firstly(
        self, addresses: Array[Address], funds: gtxn.PaymentTransaction, verifier: Application
    ) -> None:
        assert funds.receiver == Global.current_application_address, "Funds must be sent to app"

        assert addresses.length, "must provide some accounts"
        share: UInt64 = funds.amount // addresses.length

        itxn.Payment(amount=share, receiver=addresses[0].native).stage(begin_group=True)

        for i in urange(1, addresses.length):
            addr = addresses[i]
            itxn.Payment(amount=share, receiver=addr.native).stage()

        itxn.ApplicationCall(
            app_id=verifier.id, app_args=(arc4_signature("verify()void"),)
        ).stage()

        itxn.AssetConfig(asset_name="abc").stage()

        itxn.submit_staged()

    @public
    def test_looply(
        self, addresses: Array[Address], funds: gtxn.PaymentTransaction, verifier: Application
    ) -> None:
        assert funds.receiver == Global.current_application_address, "Funds must be sent to app"

        assert addresses.length, "must provide some accounts"
        share: UInt64 = funds.amount // addresses.length

        is_first = True
        for addr in addresses:
            my_txn = itxn.Payment(amount=share, receiver=addr.native)
            my_txn.stage(begin_group=is_first)
            is_first = False

        itxn.ApplicationCall(
            app_id=verifier.id, app_args=(arc4_signature("verify()void"),)
        ).stage()

        itxn.AssetConfig(asset_name="abc").stage()

        itxn.submit_staged()
