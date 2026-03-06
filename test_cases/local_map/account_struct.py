import typing

from algopy import (
    Account,
    ARC4Contract,
    Bytes,
    FixedBytes,
    LocalMap,
    StateTotals,
    Struct,
    UInt64,
    public,
)

Bytes4 = FixedBytes[typing.Literal[4]]


class Data(Struct, frozen=True):
    foo: UInt64
    bar: Bytes4


class LocalMapAccountStruct(
    ARC4Contract,
    state_totals=StateTotals(
        local_bytes=10,
    ),
):
    def __init__(self) -> None:
        self.map = LocalMap(Account, Data)

    @public(allow_actions=["OptIn"], create="require")
    def create(self) -> None:
        pass

    @public
    def get(self, account: Account, key: Account) -> Data:
        return self.map[account, key]

    @public
    def get_with_default(self, account: Account, key: Account, default: Data) -> Data:
        return self.map.get(account, key, default=default)

    @public
    def set(self, account: Account, key: Account, value: Data) -> None:
        self.map[account, key] = value

    @public
    def delete(self, account: Account, key: Account) -> None:
        del self.map[account, key]

    @public
    def in_(self, account: Account, key: Account) -> bool:
        return (account, key) in self.map

    @public
    def prefix(self) -> Bytes:
        return self.map.key_prefix

    @public
    def maybe(self, account: Account, key: Account) -> tuple[Data, bool]:
        value, exists = self.map.maybe(account, key)
        if not exists:
            # AVM actually returns a uint64 if value not present
            value = Data(foo=UInt64(), bar=Bytes4())
        return value, exists

    @public
    def get_via_state(self, account: Account, key: Account) -> Data:
        local_state = self.map.state(key)
        return local_state[account]
