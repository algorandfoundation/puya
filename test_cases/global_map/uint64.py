from algopy import ARC4Contract, Bytes, GlobalMap, StateTotals, UInt64, public


class GlobalMapUInt64(
    ARC4Contract,
    state_totals=StateTotals(
        global_uints=10,
    ),
):
    def __init__(self) -> None:
        self.map = GlobalMap(UInt64, UInt64)

    @public
    def get(self, key: UInt64) -> UInt64:
        result = self.map[key]
        map_ = GlobalMap(UInt64, UInt64, key_prefix=self.map.key_prefix)
        assert map_[key] == result
        return result

    @public
    def get_with_default(self, key: UInt64, default: UInt64) -> UInt64:
        return self.map.get(key, default=default)

    @public
    def set(self, key: UInt64, value: UInt64) -> None:
        self.map[key] = value

    @public
    def delete(self, key: UInt64) -> None:
        del self.map[key]

    @public
    def in_(self, key: UInt64) -> bool:
        return key in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, key: UInt64) -> tuple[UInt64, bool]:
        return self.map.maybe(key)

    @public
    def get_via_state(self, key: UInt64) -> UInt64:
        state = self.map.state(key)
        return state.value
