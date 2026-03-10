import pytest
from algopy import Asset, String, UInt64
from algopy_testing import algopy_testing_context
from contract import TokenManager


def _create_contract_with_asset() -> tuple[TokenManager, UInt64]:
    contract = TokenManager()
    asset_id = contract.create_asset(
        String("TestToken"),
        String("TT"),
        UInt64(1_000_000),
        UInt64(0),
        False,
    )
    return contract, asset_id


class TestCreateAsset:
    def test_stores_asset_id_and_submits_asset_config(self) -> None:
        with algopy_testing_context() as ctx:
            contract, asset_id = _create_contract_with_asset()

            assert contract.asset_id == asset_id
            assert asset_id != 0

            ac = ctx.txn.last_group.last_itxn.asset_config
            assert ac.asset_name == b"TestToken"
            assert ac.unit_name == b"TT"
            assert ac.total == 1_000_000
            assert ac.decimals == 0
            assert ac.default_frozen is False
            assert ac.created_asset.id == asset_id

    def test_rejects_non_creator_sender(self) -> None:
        with algopy_testing_context() as ctx:
            contract = TokenManager()
            non_creator = ctx.any.account()

            with (
                ctx.txn.create_group(active_txn_overrides={"sender": non_creator}),
                pytest.raises(AssertionError, match="only creator"),
            ):
                contract.create_asset(
                    String("T"),
                    String("T"),
                    UInt64(1),
                    UInt64(0),
                    False,
                )

    def test_rejects_double_creation(self) -> None:
        with algopy_testing_context():
            contract, _ = _create_contract_with_asset()

            with pytest.raises(AssertionError, match="asset already created"):
                contract.create_asset(
                    String("T2"),
                    String("T2"),
                    UInt64(1),
                    UInt64(0),
                    False,
                )


class TestOptInToAsset:
    def test_submits_zero_amount_asset_transfer(self) -> None:
        with algopy_testing_context() as ctx:
            contract, asset_id = _create_contract_with_asset()
            asset = Asset(asset_id)

            contract.opt_in_to_asset(asset)

            at = ctx.txn.last_group.last_itxn.asset_transfer
            assert at.asset_amount == 0
            assert at.xfer_asset.id == asset_id


class TestTransferAsset:
    def test_submits_asset_transfer_with_correct_receiver_and_amount(self) -> None:
        with algopy_testing_context() as ctx:
            contract, asset_id = _create_contract_with_asset()
            asset = Asset(asset_id)
            receiver = ctx.any.account()

            contract.transfer_asset(asset, receiver, UInt64(500))

            at = ctx.txn.last_group.last_itxn.asset_transfer
            assert at.xfer_asset.id == asset_id
            assert at.asset_receiver == receiver
            assert at.asset_amount == 500


class TestFreezeAccount:
    def test_submits_asset_freeze_itxn(self) -> None:
        with algopy_testing_context() as ctx:
            contract, asset_id = _create_contract_with_asset()
            asset = Asset(asset_id)
            target = ctx.any.account()

            contract.freeze_account(asset, target, True)

            af = ctx.txn.last_group.last_itxn.asset_freeze
            assert af.freeze_asset.id == asset_id
            assert af.freeze_account == target
            assert af.frozen is True


class TestClawbackAsset:
    def test_submits_asset_transfer_with_asset_sender(self) -> None:
        with algopy_testing_context() as ctx:
            contract, asset_id = _create_contract_with_asset()
            asset = Asset(asset_id)
            from_account = ctx.any.account()
            to_account = ctx.any.account()

            contract.clawback_asset(asset, from_account, to_account, UInt64(200))

            at = ctx.txn.last_group.last_itxn.asset_transfer
            assert at.xfer_asset.id == asset_id
            assert at.asset_sender == from_account
            assert at.asset_receiver == to_account
            assert at.asset_amount == 200


class TestDestroyAsset:
    def test_resets_asset_id_to_zero(self) -> None:
        with algopy_testing_context():
            contract, asset_id = _create_contract_with_asset()
            asset = Asset(asset_id)

            contract.destroy_asset(asset)

            assert contract.asset_id == 0
