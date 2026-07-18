from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Global,
    GlobalState,
    LocalState,
    OnCompleteAction,
    Txn,
    UInt64,
    arc4,
    public,
)


class AbiMethodOptions(ARC4Contract):
    """
    A tour of `@arc4.abimethod` options. Each method here is annotated with a
    different combination so it's easy to see their use cases.
    """

    def __init__(self) -> None:
        self.governor = GlobalState(Account)
        self.fee_asset = GlobalState(Asset)
        self.join_event_count = GlobalState(UInt64(0))
        self.leave_event_count = GlobalState(UInt64(0))
        self.joined_round = LocalState(UInt64)

    @arc4.abimethod(create="require")
    def create(self, governor: Account, fee_asset: Asset) -> None:
        """
        By default, an `ARC4Contract` can be created via any bare or `NoOp` call.
        Marking a method `create="require"` forces creation to go through that
        method instead, allowing constructor-style initialization with parameters.
        """
        self.governor.value = governor
        self.fee_asset.value = fee_asset

    # public is an alias for arc4.abimethod
    @public
    def public_governor_getter(self) -> Account:
        return self.governor.value

    # example: ABIMETHOD_NAME
    @arc4.abimethod(name="ping")
    def long_internal_name(self) -> arc4.String:
        """
        `name=` decouples the on-chain ABI method name from the Python
        function name. Useful for keeping the ABI surface stable while
        renaming the implementation, or for shortening selector signatures.
        """
        return arc4.String("ping")

    # example: ABIMETHOD_NAME

    # example: ABIMETHOD_READONLY
    @arc4.abimethod(readonly=True)
    def get_join_event_count(self) -> UInt64:
        """
        `readonly=True` marks the method as side-effect-free. Clients can run
        it via `simulate` without sending a real transaction. Puya does not
        enforce read-only at the bytecode level; it constitutes a promise to the
        caller.
        """
        return self.join_event_count.value

    # example: ABIMETHOD_READONLY

    # example: ABIMETHOD_DEFAULT_ARGS
    @arc4.abimethod(
        default_args={
            "fee_asset": "fee_asset",  # name of a state member
            "expected_join_event_count": get_join_event_count,  # a readonly method
        }
    )
    def admin_action(self, fee_asset: Asset, expected_join_event_count: UInt64) -> None:
        """
        `default_args=` lets a client fill arguments automatically from the
        contract's own state or readonly methods. Each value is either:
          * a string naming a storage member (state default), or
          * a reference to a `readonly=True` method (dynamic default).
        Clients that read the ABI metadata can supply the defaults on the
        user's behalf: here that means attaching the configured `fee_asset`
        resource without a separate state read, and pre-filling
        `expected_join_event_count` as an optimistic-concurrency check.
        """
        assert Txn.sender == self.governor.value, "only governor"

        # the arg is caller-supplied, so check it against the configured asset
        # before acting on it — here a mismatch is tolerated with an early
        # return rather than a failed transaction
        if fee_asset != self.fee_asset.value:
            # do some specific handling for this case
            return

        # compare-and-swap guard: reject if membership changed since observed
        assert expected_join_event_count == self.join_event_count.value, "stale join event count"
        # privileged work acting on `fee_asset` would go here

    # example: ABIMETHOD_DEFAULT_ARGS

    # example: ABIMETHOD_RESOURCE_ENCODING
    @arc4.abimethod(resource_encoding="index")
    def eligible_balance(self, asset: Asset, app: Application, account: Account) -> UInt64:
        """
        `resource_encoding="index"` (the pre-PuyaPy-5.0 behavior) tells the
        ABI router to expect resource references as a `UInt8` index into the
        foreign-array slots populated by the caller. This saves calldata when
        the same resources are reused across calls in a group.

        Without this option, the default in PuyaPy 5+ is `"value"`; the
        client passes the full Asset id / app id / account address directly,
        which is simpler and reflected in the published ABI signature.
        """
        assert account.is_opted_in(app), "account not opted in to app"
        # note: opting in creates a zero-balance holding, so this only proves the
        # account *can* hold the asset
        # use `asset.balance(account) > 0` to require an actual balance
        assert account.is_opted_in(asset), "account is not opted in to the asset"
        return asset.balance(account)

    # example: ABIMETHOD_RESOURCE_ENCODING

    # example: ABIMETHOD_ALLOW_ACTIONS
    @arc4.abimethod(allow_actions=["NoOp", "OptIn"])
    def join(self) -> None:
        """
        `allow_actions=` declares which OnComplete actions can dispatch to
        this method. The default is `["NoOp"]`. Listing `"OptIn"` here lets
        the same logic run during a NoOp call *or* an opt-in call, which is
        a handy way to bundle "first-time setup" with regular use: new
        members come in via OptIn (the network opens their local state in
        the same transaction), returning members hit the NoOp path.
        Inspect `Txn.on_completion` to branch on which one actually ran.
        """
        # Common path: every join (first or repeat) must be opted in to the fee asset
        # Even though the asset comes from state, this holding lookup still
        # requires it to be an *available resource* on the call — the AlgoKit
        # client discovers and attaches the reference automatically (via
        # simulate); a hand-rolled caller must add it to the asset references.
        assert Txn.sender.is_opted_in(self.fee_asset.value), "must be opted in to fee asset"

        # One-time setup runs only on the OptIn variant, where the sender's
        # local state has just been allocated.
        if Txn.on_completion == OnCompleteAction.OptIn:
            self.join_event_count.value += 1  # record this account's join
            self.joined_round[Txn.sender] = Global.round

    @arc4.abimethod(allow_actions=["CloseOut"])
    def opt_out(self) -> None:
        """A CloseOut handler: a member voluntarily leaving releases their
        local state, and the leave event is counted so the pair of counters
        keeps a best-effort registry: active members are approximately
        `join_event_count - leave_event_count`.

        Note: an account can always leave via a ClearState transaction, which
        cannot be blocked and bypasses this handler, so a ClearState leave is
        never recorded and the difference can overcount active members."""
        self.leave_event_count.value += 1

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        """A delete handler. Only routable from a DeleteApplication action."""
        assert Txn.sender == self.governor.value, "only governor can delete"

    # example: ABIMETHOD_ALLOW_ACTIONS
