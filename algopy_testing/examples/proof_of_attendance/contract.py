import algopy


class ProofOfAttendance(algopy.ARC4Contract):
    def __init__(self) -> None:
        self.max_attendees = algopy.UInt64(30)
        self.asset_url = algopy.String("ipfs://QmW5vERkgeJJtSY1YQdcWU6gsHCZCyLFtM1oT9uyy2WGm8")
        self.total_attendees = algopy.UInt64(0)

    @algopy.arc4.abimethod(create="require")
    def init(self, max_attendees: algopy.UInt64) -> None:
        assert algopy.Txn.sender == algopy.Global.creator_address, "Only creator can initialize"
        self.max_attendees = max_attendees

    @algopy.arc4.abimethod()
    def confirm_attendance(self) -> None:
        assert self.total_attendees < self.max_attendees, "Max attendees reached"

        minted_asset = self._mint_poa(algopy.Txn.sender)
        self.total_attendees += 1

        _id, has_claimed = algopy.op.Box.get(algopy.Txn.sender.bytes)
        assert not has_claimed, "Already claimed POA"

        algopy.op.Box.put(algopy.Txn.sender.bytes, algopy.op.itob(minted_asset.id))

    @algopy.arc4.abimethod(readonly=True)
    def get_poa_id(self) -> algopy.UInt64:
        poa_id, exists = algopy.op.Box.get(algopy.Txn.sender.bytes)
        assert exists, "POA not found"
        return algopy.op.btoi(poa_id)

    @algopy.arc4.abimethod()
    def claim_poa(self, opt_in_txn: algopy.gtxn.AssetTransferTransaction) -> None:
        poa_id, exists = algopy.op.Box.get(algopy.Txn.sender.bytes)
        assert exists, "POA not found, attendance validation failed!"
        assert opt_in_txn.xfer_asset.id == algopy.op.btoi(poa_id), "POA ID mismatch"
        assert opt_in_txn.fee == algopy.UInt64(0), "We got you covered for free!"
        assert opt_in_txn.asset_amount == algopy.UInt64(0)
        assert (
            opt_in_txn.sender == opt_in_txn.asset_receiver == algopy.Txn.sender
        ), "Opt-in transaction sender and receiver must be the same"
        assert (
            opt_in_txn.asset_close_to == opt_in_txn.rekey_to == algopy.Global.zero_address
        ), "Opt-in transaction close to must be zero address"

        self._send_poa(
            algopy.Txn.sender,
            algopy.op.btoi(poa_id),
        )

    @algopy.subroutine
    def _mint_poa(self, claimer: algopy.Account) -> algopy.Asset:
        algopy.ensure_budget(algopy.UInt64(10000), algopy.OpUpFeeSource.AppAccount)
        asset_name = b"AlgoKit POA #" + algopy.op.itob(self.total_attendees)
        return (
            algopy.itxn.AssetConfig(
                asset_name=asset_name,
                unit_name=algopy.String("POA"),
                total=algopy.UInt64(1),
                decimals=0,
                url=self.asset_url,
                manager=claimer,
            )
            .submit()
            .created_asset
        )

    @algopy.subroutine
    def _send_poa(self, receiver: algopy.Account, asset_id: algopy.UInt64) -> None:
        algopy.itxn.AssetTransfer(
            xfer_asset=asset_id,
            sender=algopy.Global.current_application_address,
            asset_receiver=receiver,
            asset_amount=1,
        ).submit()
