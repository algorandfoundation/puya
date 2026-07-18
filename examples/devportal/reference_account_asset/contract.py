from algopy import Account, ARC4Contract, Asset, TemplateVar, UInt64, arc4


# example: REFERENCE_ACCOUNT_ASSET_EXAMPLE
class ReferenceAccountAsset(ARC4Contract):
    """
    Demonstrates how to reference both an account and an asset to read an
    account's holding of a specific asset. Both references must be present
    in the transaction's reference arrays at call time (the AlgoKit client
    typically handles this automatically).
    """

    @arc4.abimethod
    def get_asset_balance(self) -> UInt64:
        """Read the asset balance for a well-known account/asset pair, baked
        into the program when it is compiled/deployed (`TMPL_KNOWN_ACCOUNT`,
        `TMPL_KNOWN_ASSET`)."""
        account = TemplateVar[Account]("KNOWN_ACCOUNT")
        asset = TemplateVar[Asset]("KNOWN_ASSET")
        assert account.is_opted_in(asset), "Account is not opted in to the asset"
        return asset.balance(account)

    @arc4.abimethod
    def get_asset_balance_with_arg(self, account: Account, asset: Asset) -> UInt64:
        """Same lookup, but with caller-supplied account and asset references."""
        assert account.is_opted_in(asset), "Account is not opted in to the asset"
        return asset.balance(account)


# example: REFERENCE_ACCOUNT_ASSET_EXAMPLE
