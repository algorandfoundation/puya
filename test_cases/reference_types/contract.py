from algopy import (
    Account,
    AccountRef,
    Application,
    ApplicationRef,
    Asset,
    AssetRef,
    ReferenceArgBehaviour,
    arc4,
)


class ReferenceTypeDemo(arc4.ARC4Contract, reference_arg_mapping=ReferenceArgBehaviour.direct):
    @arc4.abimethod
    def test_app_ref(self, app_ref: ApplicationRef, app: Application) -> None:
        assert app_ref.application == app

    @arc4.abimethod
    def test_ass_ref(self, ass_ref: AssetRef, ass: Asset) -> None:
        assert ass_ref.asset == ass

    @arc4.abimethod
    def test_acc_ref(self, acc_ref: AccountRef, acc: Account) -> None:
        assert acc_ref.account == acc
