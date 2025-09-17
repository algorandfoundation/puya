from algopy import ARC4Contract, OnCompleteAction, Txn, arc4, compile_contract, itxn, op


class Contract(ARC4Contract, avm_version=12):
    @arc4.abimethod
    def test_falcon_verify(self) -> None:
        assert not op.falcon_verify(b"", b"", op.bzero(1793))

    @arc4.abimethod
    def test_reject_version(self) -> None:
        app_v0_txn = arc4.arc4_create(ContractV0)
        app = app_v0_txn.created_app
        assert app.version == 0, "should be version 0"

        arc4.arc4_update(
            ContractV0.update, app_id=app, reject_version=1, compiled=compile_contract(ContractV1)
        )
        assert app.version == 1, "should be version 1"

        itxn.ApplicationCall(
            app_args=(
                arc4.arc4_signature(
                    ContractV1.delete,
                ),
            ),
            on_completion=OnCompleteAction.DeleteApplication,
            app_id=app,
            reject_version=2,
        ).submit()


class ContractV0(ARC4Contract, avm_version=12):
    @arc4.abimethod(allow_actions=("UpdateApplication",))
    def update(self) -> None:
        assert (
            Txn.reject_version == 1
        ), "can only update if caller expects this to be currently be v0"


class ContractV1(ARC4Contract, avm_version=12):
    @arc4.abimethod(allow_actions=("DeleteApplication",))
    def delete(self) -> None:
        assert (
            Txn.reject_version == 2
        ), "can only update if caller expects this to be currently be v1"
