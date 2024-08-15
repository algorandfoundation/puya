from algopy import ARC4Contract, Global, UInt64, arc4, gtxn, op


class AppExpectingEffects(ARC4Contract):
    @arc4.abimethod
    def create_group(
        self,
        asset_create: gtxn.AssetConfigTransaction,
        app_create: gtxn.ApplicationCallTransaction,
    ) -> tuple[UInt64, UInt64]:
        assert asset_create.created_asset.id, "expected asset created"
        assert (
            op.gaid(asset_create.group_index) == asset_create.created_asset.id
        ), "expected correct asset id"
        assert app_create.created_app.id, "expected app created"
        assert (
            op.gaid(app_create.group_index) == app_create.created_app.id
        ), "expected correct app id"

        return asset_create.created_asset.id, app_create.created_app.id

    @arc4.abimethod
    def log_group(self, app_call: gtxn.ApplicationCallTransaction) -> None:
        assert app_call.app_args(0) == arc4.arc4_signature(
            "some_value()uint64"
        ), "expected correct method called"
        assert app_call.num_logs == 1, "expected logs"
        assert (
            arc4.UInt64.from_log(app_call.last_log)
            == (app_call.group_index + 1) * Global.group_size
        )
