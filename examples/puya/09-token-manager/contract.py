"""Example 09: Token Manager

This example demonstrates inner transactions for full ASA lifecycle management.

Features:
- itxn.AssetConfig (create ASA with full address configuration)
- itxn.AssetTransfer (opt-in, transfer, clawback)
- itxn.AssetFreeze (freeze / unfreeze accounts)
- Full ASA lifecycle: create -> opt-in -> transfer -> freeze -> clawback -> destroy
- GlobalState for storing created asset reference
- Bootstrapping guard (assert to prevent double-create)

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import (
    Account,
    ARC4Contract,
    Asset,
    Global,
    Txn,
    UInt64,
    arc4,
    itxn,
)


# example: TOKEN_MANAGER
class TokenManager(ARC4Contract):
    """Manages the full lifecycle of an Algorand Standard Asset (ASA)."""

    def __init__(self) -> None:
        self.asset_id = UInt64(0)

    @arc4.abimethod
    def create_asset(
        self,
        name: arc4.String,
        unit: arc4.String,
        total: UInt64,
        decimals: UInt64,
        default_frozen: arc4.Bool,
    ) -> UInt64:
        """Create a new ASA via inner transaction.

        The contract becomes manager, reserve, freeze, and clawback authority.

        Args:
            name: Full name of the asset
            unit: Short unit name (e.g. "TKN")
            total: Total supply of the token
            decimals: Decimal places for display
            default_frozen: Whether new holders start frozen

        Returns:
            The created asset ID
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert self.asset_id == 0, "asset already created"

        result = itxn.AssetConfig(
            asset_name=name.native,
            unit_name=unit.native,
            total=total,
            decimals=decimals,
            default_frozen=default_frozen.native,
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.current_application_address,
            clawback=Global.current_application_address,
        ).submit()

        self.asset_id = result.created_asset.id
        return result.created_asset.id

    @arc4.abimethod
    def opt_in_to_asset(self, asset: Asset) -> None:
        """Opt the contract into the managed asset so it can hold tokens.

        A zero-amount self-transfer is the standard opt-in pattern.

        Args:
            asset: The managed asset to opt into
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert asset.id == self.asset_id, "wrong asset"

        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_receiver=Global.current_application_address,
            asset_amount=0,
        ).submit()

    @arc4.abimethod
    def transfer_asset(self, asset: Asset, receiver: Account, amount: UInt64) -> None:
        """Transfer tokens from the contract to a receiver.

        Args:
            asset: The managed asset to transfer
            receiver: Destination account
            amount: Number of tokens to send
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert asset.id == self.asset_id, "wrong asset"

        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_receiver=receiver,
            asset_amount=amount,
        ).submit()

    @arc4.abimethod
    def freeze_account(self, asset: Asset, account: Account, frozen: arc4.Bool) -> None:
        """Freeze or unfreeze an account's holdings of the managed asset.

        Args:
            asset: The managed asset
            account: Account to freeze/unfreeze
            frozen: true to freeze, false to unfreeze
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert asset.id == self.asset_id, "wrong asset"

        itxn.AssetFreeze(
            freeze_asset=asset,
            freeze_account=account,
            frozen=frozen.native,
        ).submit()

    @arc4.abimethod
    def clawback_asset(
        self, asset: Asset, from_account: Account, to_account: Account, amount: UInt64
    ) -> None:
        """Clawback tokens from a holder back to another account.

        Uses the asset_sender field to revoke from the target account.

        Args:
            asset: The managed asset
            from_account: Account to clawback from
            to_account: Account to receive clawed-back tokens
            amount: Amount to clawback
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert asset.id == self.asset_id, "wrong asset"

        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_sender=from_account,
            asset_receiver=to_account,
            asset_amount=amount,
        ).submit()

    @arc4.abimethod
    def destroy_asset(self, asset: Asset) -> None:
        """Destroy the managed asset.

        The contract must hold all units.

        Args:
            asset: The managed asset to destroy
        """
        assert Txn.sender == Global.creator_address, "only creator"
        assert asset.id == self.asset_id, "wrong asset"

        itxn.AssetConfig(
            config_asset=asset,
        ).submit()

        self.asset_id = UInt64(0)


# example: TOKEN_MANAGER
