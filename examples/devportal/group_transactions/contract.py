from algopy import ARC4Contract, Asset, Global, Txn, UInt64, arc4, gtxn, itxn


class GroupTransactions(ARC4Contract):
    """
    Demonstrates two complementary ways to read sibling transactions from
    the current atomic group:

    1. **Index lookup** (`gtxn.*Transaction(index)`): a runtime assertion +
       typed view. Fails the txn unless the transaction at `index` is of
       that type. Useful when the shape can't be encoded in the ABI
       signature, and may assert facts about transactions coming later
       in the group as well as before.

    2. **Typed ABI argument**: declare a `gtxn.*Transaction` directly as a
       method parameter. Transaction parameters are purely *positional*:
       they consume no space in the application args array, and the router
       binds them to the transactions immediately preceding this call, in
       declaration order, asserting each one's type before the body runs.
    """

    # example: GTXN_PAYMENT
    @arc4.abimethod
    def expect_payment(self, expected_amount: UInt64) -> UInt64:
        """
        Expects a Payment transaction immediately before this app call.
        The `gtxn.PaymentTransaction(index)` form fails if the txn at
        `index` is not a Payment (or is not present), eliminating the
        need for an explicit `Txn.type_enum` check.
        """
        pay_txn = gtxn.PaymentTransaction(Txn.group_index - 1)
        assert pay_txn.receiver == Global.current_application_address, "payment must be to app"
        assert pay_txn.amount == expected_amount, "wrong payment amount"
        return pay_txn.amount

    # example: GTXN_PAYMENT

    # example: GTXN_ASSET_TRANSFER
    @arc4.abimethod
    def expect_asset_transfer(self, asset: Asset) -> UInt64:
        """
        Expects an AssetTransfer transaction immediately before this call.
        Validates the asset id, sender, and that we (the app account) are
        the recipient.
        """
        axfer = gtxn.AssetTransferTransaction(Txn.group_index - 1)
        assert axfer.xfer_asset == asset, "wrong asset"
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "transfer must be to app"
        assert axfer.sender == Txn.sender, "transfer must come from caller"
        return axfer.asset_amount

    # example: GTXN_ASSET_TRANSFER

    @arc4.abimethod
    def opt_in_to_asset(self, asset: Asset) -> None:
        """
        Opt the application account into `asset` via an inner zero-amount
        transfer, so it can be the recipient in the `expect_asset_transfer`
        and `receive_asset_transfer` patterns above.
        """
        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_receiver=Global.current_application_address,
            asset_amount=0,
        ).submit()

    # example: GTXN_APP_CALL
    @arc4.abimethod
    def chained_app_call(self) -> UInt64:
        """
        Expects an ApplicationCall transaction immediately before this call.
        `last_log` exposes the previous app's last log entry, which lets
        chained app calls observe each other's output.
        """
        prev = gtxn.ApplicationCallTransaction(Txn.group_index - 1)
        # `arc4.UInt64.from_log(...)` decodes a typed value off the log.
        prev_count = arc4.UInt64.from_log(prev.last_log)
        return prev_count.as_uint64()

    # example: GTXN_APP_CALL

    # example: GTXN_TYPED_ARGS
    @arc4.abimethod
    def receive_funding(
        self,
        pay: gtxn.PaymentTransaction,
        axfer: gtxn.AssetTransferTransaction,
        asset: Asset,
        expected_amount: UInt64,
    ) -> UInt64:
        """
        Typed-arg form of the `expect_*` lookups, with two transaction
        parameters to show the binding rule: declaration order is group
        order, ending at this call: the group must look like
        `[..., pay, axfer, this call, ...]`, so `pay` is bound to
        `Txn.group_index - 2` and `axfer` to `Txn.group_index - 1`.
        The positions are fixed by that rule (the caller cannot choose
        them), and each position's transaction type is asserted before the
        body runs, so only the *fields* still need validating here.
        """
        assert pay.receiver == Global.current_application_address, "payment must be to app"
        assert pay.amount == expected_amount, "wrong payment amount"
        assert axfer.xfer_asset == asset, "wrong asset"
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "transfer must be to app"
        assert axfer.sender == Txn.sender, "transfer must come from caller"
        return pay.amount + axfer.asset_amount

    @arc4.abimethod
    def observe_app_call(self, prev: gtxn.ApplicationCallTransaction) -> UInt64:
        """Typed-arg form of `chained_app_call`: a single transaction
        parameter always binds to the transaction immediately preceding
        this call (`Txn.group_index - 1`), with its type asserted by the
        router. Reading `last_log` works the same as via index lookup."""
        prev_count = arc4.UInt64.from_log(prev.last_log)
        return prev_count.as_uint64()

    # example: GTXN_TYPED_ARGS

    # example: GROUP_POSITION_GUARDS
    @arc4.abimethod
    def strict_position(self, expected_size: UInt64) -> None:
        """
        Group-position guards: the `Global.group_size` and `Txn.group_index`
        properties let a contract verify its place in the group exactly.
        Useful for atomic patterns that depend on a fixed shape, e.g.
        `[Payment, AppCall, AssetTransfer]`.
        """
        assert Global.group_size == expected_size, "wrong group size"
        # This contract expects to sit at index 1 in a 3-txn group.
        assert Txn.group_index == 1, "must be index 1"

        # Reading the surrounding txns by absolute position rather than
        # relative to `group_index` is sometimes clearer.
        pay = gtxn.PaymentTransaction(0)
        axfer = gtxn.AssetTransferTransaction(2)
        assert pay.sender == axfer.asset_receiver, "sender must receive axfer"

    # example: GROUP_POSITION_GUARDS
