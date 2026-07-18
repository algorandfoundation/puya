from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Bytes,
    GlobalMap,
    GlobalState,
    StateTotals,
    String,
    UInt64,
    arc4,
    subroutine,
)


# example: GLOBAL_MAP_STRUCT
class Profile(arc4.Struct):
    """An ARC-4 struct stored as the value type of a GlobalMap."""

    name: arc4.String
    score: arc4.UInt64


# example: GLOBAL_MAP_STRUCT


class GlobalStorage(ARC4Contract):
    # example: INIT_GLOBAL_STORAGE
    def __init__(self) -> None:
        # The full form `GlobalState(UInt64(50))` declares a typed proxy and an
        # initial value. The proxy exposes `.value`, `.get(default=...)`, and
        # `.maybe()` for richer read patterns.
        self.global_int_full = GlobalState(UInt64(50))
        # The short form binds the attribute to a value directly. Reads use the
        # attribute name itself (no `.value`); there is no proxy API.
        self.global_int_simplified = UInt64(10)
        # `GlobalState(UInt64)` declares the type but leaves the slot empty
        # until it is written. Reads must go through `.maybe()` or `.get(...)`.
        self.global_int_no_default = GlobalState(UInt64)

        # example: INIT_BYTES
        self.global_bytes_full = GlobalState(Bytes(b"Hello"))
        self.global_bytes_simplified = Bytes(b"Hello")
        self.global_bytes_no_default = GlobalState(Bytes)
        # example: INIT_BYTES

        self.global_bool_simplified = True
        self.global_bool_no_default = GlobalState(bool)

        # Reference types are declared without defaults; they are populated by
        # later writes from method bodies.
        self.global_asset = GlobalState(Asset)
        self.global_application = GlobalState(Application)
        self.global_account = GlobalState(Account)

    # example: INIT_GLOBAL_STORAGE

    # example: READ_GLOBAL_STATE
    @arc4.abimethod
    def get_global_state(self) -> UInt64:
        # `.get(default=...)` returns the default when the slot is empty.
        return self.global_int_no_default.get(default=UInt64(0))

    @arc4.abimethod
    def maybe_global_state(self) -> tuple[UInt64, bool]:
        # `.maybe()` returns `(value, exists)`; when `exists` is False, `value`
        # is the type's zero value and should not be relied upon.
        value, exists = self.global_int_no_default.maybe()
        if not exists:
            value = UInt64(0)
        return value, exists

    @arc4.abimethod
    def get_global_state_example(self) -> bool:
        # The full form supports `.get(default=...)` and `.value`.
        assert self.global_int_full.get(default=UInt64(0)) == 50, "expected initial value 50"
        # The simplified form is the value itself; no proxy methods apply.
        assert self.global_int_simplified == UInt64(10), "expected initial value 10"
        assert self.global_int_no_default.get(default=UInt64(0)) == 0, "expected default 0"
        assert (
            self.global_bytes_full.get(default=Bytes(b"default")) == b"Hello"
        ), "expected initial value Hello"
        return True

    # example: READ_GLOBAL_STATE

    # example: READ_GLOBAL_STATE_EXAMPLES
    @arc4.abimethod
    def maybe_global_state_example(self) -> bool:
        int_value, int_exists = self.global_int_full.maybe()
        assert int_exists, "global_int_full should have a value"
        assert int_value == UInt64(50), "expected initial value 50"

        bytes_value, bytes_exists = self.global_bytes_full.maybe()
        assert bytes_exists, "global_bytes_full should have a value"
        assert bytes_value == b"Hello", "expected initial value Hello"

        # `no_default` slots start empty, so `.maybe()` returns False.
        _asset, asset_exists = self.global_asset.maybe()
        assert not asset_exists, "global_asset should start empty"
        return True

    # example: READ_GLOBAL_STATE_EXAMPLES

    # example: VALUE_PROPERTY_GLOBAL_STATE_EXAMPLES
    @arc4.abimethod
    def check_global_state_example(self) -> bool:
        # `.value` on a populated proxy returns the stored value directly.
        assert self.global_int_full.value == 50, "expected initial value 50"
        assert self.global_bytes_full.value == Bytes(b"Hello"), "expected initial value Hello"

        # Simplified-form attributes are just the value.
        assert self.global_int_simplified == 10, "expected initial value 10"
        assert self.global_bytes_simplified == b"Hello", "expected initial value Hello"
        assert bool(self.global_bool_simplified), "expected initial value True"

        # Truthiness on a proxy is "does the slot have a value".
        assert not self.global_int_no_default, "global_int_no_default should start empty"
        assert not self.global_bytes_no_default, "global_bytes_no_default should start empty"
        assert not self.global_bool_no_default, "global_bool_no_default should start empty"
        return True

    # example: VALUE_PROPERTY_GLOBAL_STATE_EXAMPLES

    # example: WRITE_GLOBAL_STATE
    @arc4.abimethod
    def set_global_state(self, value: Bytes) -> None:
        # `.value = ...` writes through the proxy.
        self.global_bytes_full.value = value

    # example: WRITE_GLOBAL_STATE

    # example: WRITE_GLOBAL_STATE_EXAMPLES
    @arc4.abimethod
    def set_global_state_example(
        self,
        value_bytes: Bytes,
        value_asset: Asset,
        value_app: Application,
        value_account: Account,
        *,
        value_bool: bool,
    ) -> None:
        self.global_bytes_no_default.value = value_bytes
        assert self.global_bytes_no_default.value == value_bytes, "bytes value should be stored"

        self.global_bool_no_default.value = value_bool
        assert self.global_bool_no_default.value == value_bool, "bool value should be stored"

        self.global_asset.value = value_asset
        self.global_application.value = value_app
        self.global_account.value = value_account

        # The simplified form is mutated via plain attribute assignment.
        self.global_int_simplified = UInt64(99)
        assert self.global_int_simplified == 99, "int value should be stored"

    # example: WRITE_GLOBAL_STATE_EXAMPLES

    # example: DELETE_GLOBAL_STATE
    @arc4.abimethod
    def del_global_state(self) -> bool:
        del self.global_int_full.value
        # After deletion, `.maybe()` reports the slot as empty again.
        _value, exists = self.global_int_full.maybe()
        assert not exists, "global_int_full should be empty after deletion"
        return True

    # example: DELETE_GLOBAL_STATE

    # example: DELETE_GLOBAL_STATE_EXAMPLES
    @arc4.abimethod
    def del_global_state_example(self) -> bool:
        # Deleting is idempotent: it succeeds even if the slot is already empty.
        del self.global_bytes_no_default.value
        del self.global_bool_no_default.value
        del self.global_asset.value
        return True

    # example: DELETE_GLOBAL_STATE_EXAMPLES

    @arc4.abimethod
    def pass_proxy_to_subroutine(self) -> UInt64:
        # GlobalState proxies can be passed to subroutines like any value.
        self.global_int_no_default.value = UInt64(44)
        return get_global_state_plus_1(self.global_int_no_default)

    @arc4.abimethod
    def dynamic_key_access(self) -> tuple[UInt64, Bytes]:
        # A GlobalState constructed inside a method shares the underlying
        # storage slot named by `key`. This is useful for dynamic key lookups.
        self.global_int_no_default.value = UInt64(7)
        self.global_bytes_no_default.value = Bytes(b"hi")
        return (
            read_global_uint64(Bytes(b"global_int_no_default")),
            read_global_bytes(String("global_bytes_no_default")),
        )


@subroutine
def get_global_state_plus_1(state: GlobalState[UInt64]) -> UInt64:
    """A GlobalState[T] proxy can be passed to and read from a subroutine."""
    return state.value + 1


@subroutine
def read_global_uint64(key: Bytes) -> UInt64:
    """Re-create the proxy from a dynamic key to read the underlying slot."""
    return GlobalState(UInt64, key=key).value


@subroutine
def read_global_bytes(key: String) -> Bytes:
    return GlobalState(Bytes, key=key).value


class GlobalStorageMap(
    ARC4Contract,
    state_totals=StateTotals(global_uints=16, global_bytes=16),
):
    """
    Demonstrates `GlobalMap`, a typed key→value collection backed by global
    state. Each key consumes one global-state slot, so capacity must be sized
    on the application via `algopy.StateTotals` at creation time, although
    it may be expanded throughout the app's lifecycle. The numbers
    here are the per-app maximums reserved for `scores` (uint) and `profiles`
    (bytes).
    """

    # example: INIT_GLOBAL_MAP
    def __init__(self) -> None:
        # `GlobalMap[K, V]` stores `V` keyed by `K` in global state.
        # `key_prefix` is prepended to every stored key; it defaults to the
        # attribute name when omitted.
        self.scores = GlobalMap(arc4.String, UInt64)
        self.profiles = GlobalMap(UInt64, Profile, key_prefix="profile")

    # example: INIT_GLOBAL_MAP

    # example: READ_GLOBAL_MAP
    @arc4.abimethod
    def get_score(self, name: arc4.String) -> UInt64:
        # Indexing reads the slot for `name`; fails if not present.
        return self.scores[name]

    @arc4.abimethod
    def get_score_or_default(self, name: arc4.String) -> UInt64:
        # `.get(key, default=...)` returns the default if the key is missing.
        return self.scores.get(name, default=UInt64(0))

    @arc4.abimethod
    def maybe_score(self, name: arc4.String) -> tuple[UInt64, bool]:
        # `.maybe(key)` returns `(value, exists)`.
        return self.scores.maybe(name)

    @arc4.abimethod
    def has_profile(self, user_id: UInt64) -> bool:
        # `key in map` is True if the key has a stored value.
        return user_id in self.profiles

    # example: READ_GLOBAL_MAP

    # example: WRITE_GLOBAL_MAP
    @arc4.abimethod
    def set_score(self, name: arc4.String, score: UInt64) -> None:
        self.scores[name] = score

    @arc4.abimethod
    def set_profile(self, user_id: UInt64, profile: Profile) -> None:
        # ARC-4 Structs are reference-like; `.copy()` ensures the map owns its bytes.
        self.profiles[user_id] = profile.copy()

    # example: WRITE_GLOBAL_MAP

    # example: DELETE_GLOBAL_MAP
    @arc4.abimethod
    def delete_score(self, name: arc4.String) -> None:
        del self.scores[name]

    # example: DELETE_GLOBAL_MAP

    @arc4.abimethod
    def get_slot_proxy(self, name: arc4.String) -> UInt64:
        # `.state(key)` returns a `GlobalState[V]` proxy for a single slot,
        # which can be passed to subroutines or used with `.value`, `.maybe()`, etc.
        slot = self.scores.state(name)
        return slot.value
