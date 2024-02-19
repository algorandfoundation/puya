from puyapy import (
    Bytes,
    arc4,
    gtxn,
    op,
    subroutine,
    uenumerate,
)


class TransactionContract(arc4.ARC4Contract):
    @arc4.abimethod(create=True)
    def create(self) -> None:
        pass

    @subroutine
    def _common_checks(self, txn: gtxn.TransactionBase) -> None:
        assert txn.txn_id, "txn_id"
        assert txn.sender == op.Global.creator_address, "sender"
        assert txn.fee, "fee"
        assert txn.type, "type"
        assert txn.type_bytes, "type_bytes"
        assert txn.note == Bytes(b""), "note"
        assert txn.group_index == 0, "group_index"
        assert txn.first_valid, "first_valid"
        # assert txn.first_valid_time, "first_valid_time" # this value can be flaky in tests
        assert txn.last_valid, "last_valid"
        assert txn.lease, "lease"
        assert txn.rekey_to == op.Global.zero_address, "rekey_to"

    @arc4.abimethod
    def pay(self, txn: gtxn.PaymentTransaction) -> None:
        self._common_checks(txn)
        assert (
            txn.receiver == op.Global.current_application_address
        ), "Payment should be for this app"
        assert txn.amount > 1000, "Payment should be for >1000 micro algos"
        assert txn.close_remainder_to == op.Global.zero_address, "close_remainder_to"

    @arc4.abimethod
    def key(self, txn: gtxn.KeyRegistrationTransaction) -> None:
        self._common_checks(txn)
        assert txn.vote_key, "vote_key"
        assert txn.selection_key, "selection_key"
        assert txn.vote_key_dilution, "vote_key_dilution"
        assert txn.vote_first, "vote_first"
        assert txn.vote_last, "vote_last"
        assert txn.non_participation, "non_participation"
        assert txn.state_proof_key, "state_proof_key"

    @arc4.abimethod
    def asset_config(self, txn: gtxn.AssetConfigTransaction) -> None:
        self._common_checks(txn)

        assert txn.config_asset, "config_asset"
        assert txn.total, "total"
        assert txn.decimals, "decimals"
        assert txn.default_frozen, "default_frozen"
        assert txn.unit_name, "unit_name"
        assert txn.asset_name, "asset_name"
        assert txn.url, "url"
        assert txn.metadata_hash, "metadata_hash"
        assert txn.manager, "manager"
        assert txn.reserve, "reserve"
        assert txn.freeze, "freeze"
        assert txn.clawback, "clawback"

    @arc4.abimethod
    def asset_transfer(self, txn: gtxn.AssetTransferTransaction) -> None:
        self._common_checks(txn)
        assert txn.xfer_asset, "xfer_asset"
        assert txn.asset_amount, "asset_amount"
        assert txn.asset_sender, "asset_sender"
        assert txn.asset_receiver, "asset_receiver"
        assert txn.asset_close_to, "asset_close_to"

    @arc4.abimethod
    def asset_freeze(self, txn: gtxn.AssetFreezeTransaction) -> None:
        self._common_checks(txn)

        assert txn.freeze_asset, "freeze_asset"
        assert txn.freeze_account, "freeze_account"
        assert txn.frozen, "frozen"

    @arc4.abimethod
    def application_call(self, txn: gtxn.ApplicationCallTransaction) -> None:
        self._common_checks(txn)
        assert txn.app_id, "app_id"
        assert txn.on_completion, "on_completion"
        assert txn.num_app_args, "num_app_args"
        assert txn.num_accounts, "num_accounts"
        assert txn.approval_program, "approval_program"
        assert txn.clear_state_program, "clear_state_program"
        assert txn.num_assets, "num_assets"
        assert txn.num_apps, "num_apps"
        assert txn.global_num_uint, "global_num_uint"
        assert txn.global_num_byte_slice, "global_num_byte_slice"
        assert txn.local_num_uint, "local_num_uint"
        assert txn.local_num_byte_slice, "local_num_byte_slice"
        assert txn.extra_program_pages, "extra_program_pages"
        assert txn.last_log, "last_log"
        assert txn.num_approval_program_pages, "num_approval_program_pages"
        assert txn.num_clear_state_program_pages, "num_clear_state_program_pages"
        assert txn.app_args(0), "app_args(0)"
        assert txn.accounts(0), "accounts(0)"
        assert txn.assets(0), "assets(0)"
        assert txn.apps(0), "apps(0)"
        assert txn.approval_program_pages(0), "approval_program_pages(0)"
        assert txn.clear_state_program_pages(0), "clear_state_program_pages(0)"

    @arc4.abimethod
    def multiple_txns(
        self,
        txn1: gtxn.ApplicationCallTransaction,
        txn2: gtxn.ApplicationCallTransaction,
        txn3: gtxn.ApplicationCallTransaction,
    ) -> None:
        for index, app in uenumerate((txn1, txn2, txn3)):
            assert app.group_index == index

    @arc4.abimethod
    def any_txn(
        self,
        _txn1: gtxn.ApplicationCallTransaction,
        _txn2: gtxn.ApplicationCallTransaction,
        _txn3: gtxn.ApplicationCallTransaction,
    ) -> None:
        txn1 = gtxn.Transaction(0)
        txn2 = gtxn.Transaction(1)
        txn3 = gtxn.Transaction(2)
        for index, txn in uenumerate((txn1, txn2, txn3)):
            assert txn.group_index == index
