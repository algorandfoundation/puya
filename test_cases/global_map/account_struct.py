import typing

from algopy import (
    Account,
    ARC4Contract,
    Bytes,
    FixedBytes,
    GlobalMap,
    StateTotals,
    Struct,
    UInt64,
    public,
)

Bytes4 = FixedBytes[typing.Literal[4]]


class Data(Struct, frozen=True):
    foo: UInt64
    bar: Bytes4


class GlobalMapAccountStruct(
    ARC4Contract,
    state_totals=StateTotals(
        global_bytes=10,
    ),
):
    def __init__(self) -> None:
        self.map = GlobalMap(Account, Data)

    @public
    def get(self, key: Account) -> Data:
        return self.map[key]

    @public
    def get_with_default(self, key: Account, default: Data) -> Data:
        return self.map.get(key, default=default)

    @public
    def set(self, key: Account, value: Data) -> None:
        self.map[key] = value

    @public
    def delete(self, key: Account) -> None:
        del self.map[key]

    @public
    def in_(self, key: Account) -> bool:
        return key in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, key: Account) -> tuple[Data, bool]:
        value, exists = self.map.maybe(key)
        if not exists:
            # AVM actually returns a uint64 if value not present
            value = Data(foo=UInt64(), bar=Bytes4())
        return value, exists

    @public
    def get_via_state(self, key: Account) -> Data:
        state = self.map.state(key)
        return state.value
