import typing

from algopy import (
    Application,
    ARC4Contract,
    Array,
    Box,
    FixedBytes,
    Remote,
    UInt64,
    public,
    subroutine,
    urange,
)

ArrayU64 = Array[UInt64]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


@subroutine
def _box(app: Application) -> Box[ArrayU64, Remote]:
    # a box of another application is not this contract's state, so unlike the local
    # equivalent it can't be a member - it is constructed wherever it is used instead
    return Box.remote(ArrayU64, app=app, key=b"box")


class RemoteArrayUInt64(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = ArrayU64()

    @public
    def append(self, app: Application, value: UInt64) -> None:
        _box(app).value.append(value)

    @public
    def concat(self, app: Application, array: ArrayU64) -> None:
        _box(app).value.extend(array)

    @public
    def pop(self, app: Application) -> UInt64:
        return _box(app).value.pop()

    @public
    def get(self, app: Application, idx: UInt64) -> UInt64:
        return _box(app).value[idx]

    @public
    def set(self, app: Application, idx: UInt64, value: UInt64) -> None:
        _box(app).value[idx] = value

    @public
    def verify(self, app: Application, expected: ArrayU64) -> None:
        # rather than asserting box.value directly (which would attempt to load the whole box)
        # assert the length and individual items
        assert _box(app).value.length == expected.length
        for i in urange(expected.length):
            assert _box(app).value[i] == expected[i]
