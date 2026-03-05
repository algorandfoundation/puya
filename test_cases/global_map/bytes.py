from algopy import ARC4Contract, Bytes, GlobalMap, StateTotals, public


class GlobalMapBytes(
    ARC4Contract,
    state_totals=StateTotals(
        global_bytes=10,
    ),
):
    def __init__(self) -> None:
        self.map = GlobalMap(Bytes, Bytes)

    @public
    def get(self, key: Bytes) -> Bytes:
        return self.map[key]

    @public
    def get_with_default(self, key: Bytes, default: Bytes) -> Bytes:
        return self.map.get(key, default=default)

    @public
    def set(self, key: Bytes, value: Bytes) -> None:
        self.map[key] = value

    @public
    def delete(self, key: Bytes) -> None:
        del self.map[key]

    @public
    def in_(self, key: Bytes) -> bool:
        return key in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, key: Bytes) -> tuple[Bytes, bool]:
        value, exists = self.map.maybe(key)
        if not exists:
            # AVM actually returns a uint64 if value not present
            value = Bytes()
        return value, exists

    @public
    def get_via_state(self, key: Bytes) -> Bytes:
        state = self.map.state(key)
        return state.value
