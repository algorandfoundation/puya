from algopy import Account, ARC4Contract, Bytes, LocalMap, StateTotals, UInt64, public


class LocalMapUInt64(
    ARC4Contract,
    state_totals=StateTotals(
        local_uints=10,
    ),
):
    def __init__(self) -> None:
        self.map = LocalMap(UInt64, UInt64)

    @public(allow_actions=["OptIn"], create="require")
    def create(self) -> None:
        pass

    @public
    def get(self, account: Account, key: UInt64) -> UInt64:
        return self.map[account, key]

    @public
    def get_with_default(self, account: Account, key: UInt64, default: UInt64) -> UInt64:
        return self.map.get(account, key, default=default)

    @public
    def set(self, account: Account, key: UInt64, value: UInt64) -> None:
        self.map[account, key] = value

    @public
    def delete(self, account: Account, key: UInt64) -> None:
        del self.map[account, key]

    @public
    def in_(self, account: Account, key: UInt64) -> bool:
        return (account, key) in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, account: Account, key: UInt64) -> tuple[UInt64, bool]:
        return self.map.maybe(account, key)

    @public
    def get_via_state(self, account: Account, key: UInt64) -> UInt64:
        state = self.map.state(key)
        return state[account]
