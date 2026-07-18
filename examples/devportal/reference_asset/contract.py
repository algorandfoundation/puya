from algopy import ARC4Contract, Asset, TemplateVar, UInt64, arc4


# example: GET_ASSET_REFERENCE_EXAMPLE
class ReferenceAsset(ARC4Contract):
    """
    Demonstrates accessing properties of an external asset. The asset is
    either baked into the program via a template variable or supplied as a
    method argument. Either way, it must be present in the transaction's
    reference array at call time (the AlgoKit client typically handles this
    automatically).
    """

    @arc4.abimethod
    def get_asset_total_supply(self) -> UInt64:
        """Read the total supply of a well-known asset, baked into the program
        when it is compiled/deployed (`TMPL_KNOWN_ASSET`)."""
        asset = TemplateVar[Asset]("KNOWN_ASSET")
        return asset.total

    @arc4.abimethod
    def get_asset_total_supply_with_arg(self, asset: Asset) -> UInt64:
        """Same lookup, but with a caller-supplied asset reference."""
        return asset.total


# example: GET_ASSET_REFERENCE_EXAMPLE
