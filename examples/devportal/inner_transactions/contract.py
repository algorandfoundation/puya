from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Global,
    String,
    Txn,
    UInt64,
    arc4,
    compile_contract,
    itxn,
)


class HelloWorldContract(ARC4Contract):
    """
    A minimal callee used by `InnerTransactions.deploy_app` and friends.
    Kept in this file so the example is self-contained.
    """

    @arc4.abimethod
    def hello(self, name: String) -> String:
        return "Hello, " + name


class InnerTransactions(ARC4Contract):
    # example: PAYMENT
    @arc4.abimethod
    def payment(self) -> UInt64:
        """
        The inner transaction `fee` defaults to 0, so the outer transaction must cover
        it; it is only set explicitly here for demonstration purposes.
        The sender is implied to be `Global.current_application_address`.

        If a different sender is needed, it'd have to be an account that has been
        rekeyed to the application address.
        """
        result = itxn.Payment(amount=5000, receiver=Txn.sender, fee=0).submit()
        return result.amount

    # example: PAYMENT

    # example: ASSET_CREATE
    @arc4.abimethod
    def fungible_asset_create(self) -> UInt64:
        itxn_result = itxn.AssetConfig(
            total=100_000_000_000,
            decimals=2,
            unit_name="RP",
            asset_name="Royalty Points",
        ).submit()
        return itxn_result.created_asset.id

    @arc4.abimethod
    def non_fungible_asset_create(self) -> UInt64:
        """
        Following the ARC3 standard, a non-fungible asset must have an on-chain total
        supply of exactly 1 whole unit. For fractional NFTs that means
        `total` must equal 10^`decimals`.
        Example: total=100, decimals=2 -> 100 * 0.01 = 1 whole unit
        """
        itxn_result = itxn.AssetConfig(
            total=100,
            decimals=2,
            unit_name="ML",
            asset_name="Mona Lisa",
            url="https://link_to_ipfs/Mona_Lisa",
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.current_application_address,
            clawback=Global.current_application_address,
        ).submit()
        return itxn_result.created_asset.id

    # example: ASSET_CREATE

    # example: ASSET_OPT_IN
    @arc4.abimethod
    def asset_opt_in(self, asset: Asset) -> None:
        """
        A zero amount asset transfer to one's self is a special type of asset transfer
        that is used to opt-in to an asset.

        To send an asset transfer, the asset must be an available resource.
        Refer to the Resource Availability section for more information.
        """
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
            asset_amount=0,
        ).submit()

    # example: ASSET_OPT_IN

    # example: ASSET_TRANSFER
    @arc4.abimethod
    def asset_transfer(self, asset: Asset, receiver: Account, amount: UInt64) -> None:
        """
        For a smart contract to transfer an asset, the app account must be opted into it,
        and be holding a non zero amount of said asset.

        To send an asset transfer, the asset must be an available resource.
        Refer to the Resource Availability section for more information.
        """
        itxn.AssetTransfer(
            asset_receiver=receiver,
            xfer_asset=asset,
            asset_amount=amount,
        ).submit()

    # example: ASSET_TRANSFER

    # example: ASSET_FREEZE
    @arc4.abimethod
    def asset_freeze(self, acct_to_be_frozen: Account, asset: Asset) -> None:
        """The asset must have an account with freeze authority."""
        itxn.AssetFreeze(
            freeze_account=acct_to_be_frozen,
            freeze_asset=asset,
            frozen=True,
        ).submit()

    # example: ASSET_FREEZE

    # example: ASSET_REVOKE
    @arc4.abimethod
    def asset_revoke(self, asset: Asset, account_to_be_revoked: Account, amount: UInt64) -> None:
        """
        To revoke an asset, the asset must be a revocable asset
        by having an account with clawback authority.

        Sender is implied to be current_application_address.
        """
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
            asset_sender=account_to_be_revoked,
            asset_amount=amount,
        ).submit()

    # example: ASSET_REVOKE

    # example: ASSET_CONFIG
    @arc4.abimethod
    def asset_config(self, asset: Asset) -> None:
        itxn.AssetConfig(
            config_asset=asset,
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Txn.sender,
            clawback=Txn.sender,
        ).submit()

    # example: ASSET_CONFIG

    # example: ASSET_DELETE
    @arc4.abimethod
    def asset_delete(self, asset: Asset) -> None:
        itxn.AssetConfig(config_asset=asset).submit()

    # example: ASSET_DELETE

    # example: GROUPED_INNER_TXNS
    @arc4.abimethod
    def multi_inner_txns(self, app_id: Application) -> tuple[UInt64, String]:
        payment_params = itxn.Payment(amount=5000, receiver=Txn.sender)
        app_call_params = itxn.ApplicationCall(
            app_id=app_id,
            app_args=(arc4.arc4_signature("hello(string)string"), arc4.String("World")),
        )

        pay_txn, app_call_txn = itxn.submit_txns(payment_params, app_call_params)

        # `arc4.String.from_log(...)` decodes a typed value off the log;
        # `.native` converts it to the native `String` type.
        hello_world_result = arc4.String.from_log(app_call_txn.last_log)
        return pay_txn.amount, hello_world_result.native

    # example: GROUPED_INNER_TXNS

    # example: DEPLOY_APP
    @arc4.abimethod
    def deploy_app(self) -> UInt64:
        """Deploy `HelloWorldContract` via a low-level `itxn.ApplicationCall`."""
        compiled = compile_contract(HelloWorldContract)
        app_txn = itxn.ApplicationCall(
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
        ).submit()
        return app_txn.created_app.id

    @arc4.abimethod
    def arc4_deploy_app(self) -> UInt64:
        """Deploy `HelloWorldContract` via the higher-level `arc4.arc4_create`."""
        app_txn = arc4.arc4_create(HelloWorldContract)
        return app_txn.created_app.id

    # example: DEPLOY_APP

    # example: NOOP_APP_CALL
    @arc4.abimethod
    def noop_app_call(self, app_id: Application) -> tuple[String, String]:
        # Manually-constructed app call: caller must encode args and decode logs.
        call_txn = itxn.ApplicationCall(
            app_id=app_id,
            app_args=(arc4.arc4_signature("hello(string)string"), arc4.String("World")),
        ).submit()
        first_hello_world_result = arc4.String.from_log(call_txn.last_log).native

        # `arc4.abi_call` infers the signature from the typed method reference
        # and handles argument encoding and return decoding automatically.
        second_hello_world_result, _txn = arc4.abi_call(
            HelloWorldContract.hello,
            "again",
            app_id=app_id,
        )

        return first_hello_world_result, second_hello_world_result

    # example: NOOP_APP_CALL
