from algopy import Account, ARC4Contract, Bytes, LocalMap, StateTotals, public


class LocalMapBytes(
    ARC4Contract,
    state_totals=StateTotals(
        local_bytes=10,
    ),
):
    def __init__(self) -> None:
        self.map = LocalMap(Bytes, Bytes)

    @public(allow_actions=["OptIn"], create="require")
    def create(self) -> None:
        pass

    @public
    def get(self, account: Account, key: Bytes) -> Bytes:
        return self.map[account, key]

    @public
    def get_with_default(self, account: Account, key: Bytes, default: Bytes) -> Bytes:
        return self.map.get(account, key, default=default)

    @public
    def set(self, account: Account, key: Bytes, value: Bytes) -> None:
        self.map[account, key] = value

    @public
    def delete(self, account: Account, key: Bytes) -> None:
        del self.map[account, key]

    @public
    def in_(self, account: Account, key: Bytes) -> bool:
        return (account, key) in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, account: Account, key: Bytes) -> tuple[Bytes, bool]:
        value, exists = self.map.maybe(account, key)
        if not exists:
            # AVM actually returns a uint64 if value not present
            value = Bytes()
        return value, exists

    @public
    def get_via_state(self, account: Account, key: Bytes) -> Bytes:
        state = self.map.state(key)
        return state[account]
