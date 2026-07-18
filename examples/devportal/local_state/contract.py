from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    LocalMap,
    LocalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
    subroutine,
)


class LocalStorage(ARC4Contract):
    # example: INIT_LOCAL_STORAGE
    def __init__(self) -> None:
        # `LocalState(T)` declares a per-account storage slot of type T.
        # Each opted-in account gets an independent value at this key.
        self.local_int = LocalState(UInt64)
        self.local_bytes = LocalState(Bytes)
        self.local_bool = LocalState(bool)
        self.local_asset = LocalState(Asset)
        self.local_application = LocalState(Application)
        self.local_account = LocalState(Account)

    # example: INIT_LOCAL_STORAGE

    @arc4.abimethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        """Accounts must opt in before their local state slots can be written."""
        self.local_int[Txn.sender] = UInt64(10)
        self.local_bytes[Txn.sender] = Bytes(b"Hello")
        self.local_bool[Txn.sender] = True
        self.local_asset[Txn.sender] = Asset(10)
        self.local_application[Txn.sender] = Application(10)
        self.local_account[Txn.sender] = Global.zero_address

    # example: CONTAIN_PROPERTY_LOCAL_STATE
    @arc4.abimethod
    def contains_local_data(self, for_account: Account) -> bool:
        # `account in state` is True if the account has a value at this slot.
        return for_account in self.local_int

    # example: CONTAIN_PROPERTY_LOCAL_STATE

    # example: CONTAIN_PROPERTY_LOCAL_STATE_EXAMPLES
    @arc4.abimethod
    def contains_local_data_example(self, for_account: Account) -> bool:
        assert for_account in self.local_int, "no local_int for account"
        assert for_account in self.local_bytes, "no local_bytes for account"
        assert for_account in self.local_bool, "no local_bool for account"
        assert for_account in self.local_asset, "no local_asset for account"
        assert for_account in self.local_application, "no local_application for account"
        assert for_account in self.local_account, "no local_account for account"
        return True

    # example: CONTAIN_PROPERTY_LOCAL_STATE_EXAMPLES

    # example: READ_LOCAL_STATE
    @arc4.abimethod
    def get_item_local_data(self, for_account: Account) -> UInt64:
        # `state[account]` returns the stored value; fails if the account has none.
        return self.local_int[for_account]

    @arc4.abimethod
    def get_local_data_with_default_int(self, for_account: Account) -> UInt64:
        # `.get(account, default=...)` returns the default if no value exists.
        return self.local_int.get(for_account, default=UInt64(0))

    @arc4.abimethod
    def maybe_local_data(self, for_account: Account) -> tuple[UInt64, bool]:
        # `.maybe(account)` returns `(value, exists)`; when `exists` is False,
        # `value` is the type's zero value and should not be relied upon.
        result, exists = self.local_int.maybe(for_account)
        if not exists:
            result = UInt64(0)
        return result, exists

    # example: READ_LOCAL_STATE

    # example: READ_LOCAL_STATE_EXAMPLES
    @arc4.abimethod
    def get_item_local_data_example(self, for_account: Account) -> bool:
        assert self.local_int[for_account] == UInt64(10), "expected opt-in value 10"
        assert self.local_bytes[for_account] == b"Hello", "expected opt-in value Hello"
        assert bool(self.local_bool[for_account]), "expected opt-in value True"
        assert self.local_asset[for_account] == Asset(10), "expected opt-in asset 10"
        assert self.local_application[for_account] == Application(10), "expected opt-in app 10"
        assert (
            self.local_account[for_account] == Global.zero_address
        ), "expected opt-in zero address"
        return True

    @arc4.abimethod
    def get_local_data_with_default(self, for_account: Account) -> bool:
        assert self.local_int.get(for_account, default=UInt64(0)) == UInt64(
            10
        ), "expected opt-in value 10"
        assert self.local_bytes.get(for_account, default=Bytes(b"Default Value")) == Bytes(
            b"Hello"
        ), "expected opt-in value Hello"
        assert bool(self.local_bool.get(for_account, default=False)), "expected opt-in value True"
        assert self.local_asset.get(for_account, default=Asset(0)) == Asset(
            10
        ), "expected opt-in asset 10"
        assert self.local_application.get(for_account, default=Application(0)) == Application(
            10
        ), "expected opt-in app 10"
        assert (
            self.local_account.get(for_account, default=Global.zero_address) == Global.zero_address
        ), "expected opt-in zero address"
        return True

    @arc4.abimethod
    def maybe_local_data_example(self, for_account: Account) -> bool:
        result, exists = self.local_int.maybe(for_account)
        assert exists, "no data for account"
        assert result == UInt64(10), "expected opt-in value 10"
        return True

    # example: READ_LOCAL_STATE_EXAMPLES

    # example: WRITE_LOCAL_STATE
    @arc4.abimethod
    def set_local_int(self, for_account: Account, value: UInt64) -> None:
        # `state[account] = value` writes the per-account slot.
        self.local_int[for_account] = value

    # example: WRITE_LOCAL_STATE

    # example: WRITE_LOCAL_STATE_EXAMPLES
    @arc4.abimethod
    def set_local_data_example(
        self,
        for_account: Account,
        value_asset: Asset,
        value_account: Account,
        value_app: Application,
        value_bytes: Bytes,
        *,
        value_bool: bool,
    ) -> bool:
        self.local_bytes[for_account] = value_bytes
        assert self.local_bytes[for_account] == value_bytes, "bytes value should be stored"

        self.local_bool[for_account] = value_bool
        assert self.local_bool[for_account] == value_bool, "bool value should be stored"

        self.local_asset[for_account] = value_asset
        assert self.local_asset[for_account] == value_asset, "asset value should be stored"

        self.local_application[for_account] = value_app
        assert self.local_application[for_account] == value_app, "app value should be stored"

        self.local_account[for_account] = value_account
        assert self.local_account[for_account] == value_account, "account value should be stored"
        return True

    # example: WRITE_LOCAL_STATE_EXAMPLES

    # example: DELETE_LOCAL_STATE
    @arc4.abimethod
    def delete_local_data(self, for_account: Account) -> None:
        # `del state[account]` removes the per-account value.
        del self.local_int[for_account]

    # example: DELETE_LOCAL_STATE

    # example: DELETE_LOCAL_STATE_EXAMPLES
    @arc4.abimethod
    def delete_local_data_example(self, for_account: Account) -> bool:
        # Deleting is idempotent: it succeeds even if the slot is already empty.
        del self.local_int[for_account]
        del self.local_bytes[for_account]
        del self.local_bool[for_account]
        del self.local_asset[for_account]
        del self.local_application[for_account]
        del self.local_account[for_account]
        return True

    # example: DELETE_LOCAL_STATE_EXAMPLES

    @arc4.abimethod
    def pass_proxy_to_subroutine(self, for_account: Account) -> UInt64:
        # LocalState proxies can be passed to subroutines like any value.
        return read_local_int_plus_1(self.local_int, for_account)


@subroutine
def read_local_int_plus_1(state: LocalState[UInt64], account: Account) -> UInt64:
    """A LocalState[T] proxy can be passed to and read from a subroutine."""
    return state[account] + 1


class LocalStorageMap(ARC4Contract, state_totals=StateTotals(local_uints=16)):
    """
    Demonstrates `LocalMap`, a typed key→value collection in each opted-in
    account's local state. Capacity may be sized on the application via
    `algopy.StateTotals` at creation time, and it may be decreased or increased
    throughout the application's lifecycle. The number here is the per-account
    maximum reserved for `balances` and `flags` combined.

    `LocalMap` lookups are indexed by a `(account, key)` tuple: one logical
    map shared by all accounts, with values partitioned by account.
    """

    # example: INIT_LOCAL_MAP
    def __init__(self) -> None:
        # `LocalMap[K, V]` stores `V` keyed by `K` in each account's local state.
        # The `key_prefix` defaults to the attribute name when omitted.
        self.balances = LocalMap(arc4.String, UInt64)
        self.flags = LocalMap(UInt64, bool, key_prefix="flag")

    # example: INIT_LOCAL_MAP

    @arc4.abimethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        # Accounts must opt in before any per-account slot is writable.
        self.balances[Txn.sender, arc4.String("USD")] = UInt64(100)
        self.flags[Txn.sender, UInt64(0)] = True

    # example: READ_LOCAL_MAP
    @arc4.abimethod
    def get_balance(self, account: Account, currency: arc4.String) -> UInt64:
        # Indexing reads the slot for `(account, key)`; fails if not present.
        return self.balances[account, currency]

    @arc4.abimethod
    def get_balance_or_default(self, account: Account, currency: arc4.String) -> UInt64:
        # `.get(account, key, default=...)` returns the default if missing.
        return self.balances.get(account, currency, default=UInt64(0))

    @arc4.abimethod
    def maybe_balance(self, account: Account, currency: arc4.String) -> tuple[UInt64, bool]:
        return self.balances.maybe(account, currency)

    @arc4.abimethod
    def has_flag(self, account: Account, key: UInt64) -> bool:
        # `(account, key) in map` is True if the slot has a stored value.
        return (account, key) in self.flags

    # example: READ_LOCAL_MAP

    # example: WRITE_LOCAL_MAP
    @arc4.abimethod
    def set_balance(self, account: Account, currency: arc4.String, value: UInt64) -> None:
        self.balances[account, currency] = value

    @arc4.abimethod
    def set_flag(self, account: Account, key: UInt64, *, value: bool) -> None:
        self.flags[account, key] = value

    # example: WRITE_LOCAL_MAP

    # example: DELETE_LOCAL_MAP
    @arc4.abimethod
    def delete_balance(self, account: Account, currency: arc4.String) -> None:
        del self.balances[account, currency]

    # example: DELETE_LOCAL_MAP

    @arc4.abimethod
    def get_slot_proxy(self, account: Account, currency: arc4.String) -> UInt64:
        # `.state(key)` returns a `LocalState[V]` proxy for that key,
        # which still requires an account to dereference.
        slot = self.balances.state(currency)
        return slot[account]
