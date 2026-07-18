from algopy import (
    Account,
    Application,
    ARC4Contract,
    Global,
    LocalState,
    TemplateVar,
    Txn,
    UInt64,
    arc4,
    op,
)


class MyCounter(ARC4Contract):
    """
    A reusable counter app held in each opted-in account's local state.
    Accounts must opt in before the counter is readable or writable.
    """

    def __init__(self) -> None:
        self.my_counter = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        self.my_counter[Txn.sender] = UInt64(0)

    @arc4.abimethod
    def increment_my_counter(self) -> UInt64:
        assert Txn.sender.is_opted_in(
            Global.current_application_id
        ), "Account is not opted in to the app"
        self.my_counter[Txn.sender] += 1
        return self.my_counter[Txn.sender]


# example: REFERENCE_ACCOUNT_APP_EXAMPLE
class ReferenceAccountApp(ARC4Contract):
    """
    Demonstrates reading another application's per-account local state.
    The referenced account and application must both appear in the
    transaction's reference arrays at call time (the AlgoKit client
    typically handles this automatically).
    """

    @arc4.abimethod
    def get_my_counter(self) -> UInt64:
        """Read a counter from a well-known account/app pair, baked into the
        program when it is compiled/deployed (`TMPL_KNOWN_ACCOUNT`,
        `TMPL_KNOWN_APP`)."""
        account = TemplateVar[Account]("KNOWN_ACCOUNT")
        app = TemplateVar[Application]("KNOWN_APP")

        # reading another app's local state requires the low-level AppLocal.get_ex_* ops;
        # the high-level LocalState type only covers the current application's state.
        # note: if the account is not opted in to the app at all, the opcode itself
        # fails the program — `exists` is False only when the account *is* opted in
        # but the key has not been set
        my_count, exists = op.AppLocal.get_ex_uint64(account, app, b"my_counter")
        assert exists, "my_counter is not set for this account"
        return my_count

    @arc4.abimethod
    def get_my_counter_with_arg(self, account: Account, app: Application) -> UInt64:
        """Same lookup, but with caller-supplied account and app references."""
        my_count, exists = op.AppLocal.get_ex_uint64(account, app, b"my_counter")
        assert exists, "my_counter is not set for this account"
        return my_count


# example: REFERENCE_ACCOUNT_APP_EXAMPLE
