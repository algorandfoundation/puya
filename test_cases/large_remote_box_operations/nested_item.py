import typing

from algopy import (
    Application,
    ARC4Contract,
    Array,
    Box,
    FixedBytes,
    Remote,
    Struct,
    UInt64,
    public,
    subroutine,
)

Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class Child(Struct, frozen=True):
    uint: UInt64
    bool_: bool


class Parent(Struct, frozen=True):
    child: Child
    bar: UInt64


class GrandParent(Struct):
    a: UInt64
    arr: Array[Parent]
    b: UInt64


class ItemWithArray(Struct):
    arr: Array[UInt64]


class StructWithNestedArray(Struct):
    grand: GrandParent
    padding: LargeBytes
    items: Array[ItemWithArray]


@subroutine
def _box(app: Application) -> Box[StructWithNestedArray, Remote]:
    return Box.remote(StructWithNestedArray, app=app, key=b"box")


class RemoteNestedItemArrayUInt64(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = StructWithNestedArray(
            grand=GrandParent(
                a=UInt64(1),
                arr=Array(
                    (
                        Parent(
                            child=Child(
                                uint=UInt64(42),
                                bool_=True,
                            ),
                            bar=UInt64(123),
                        ),
                    )
                ),
                b=UInt64(2),
            ),
            padding=LargeBytes(),
            items=Array[ItemWithArray](),
        )
        _box(app).value.items.append(ItemWithArray(arr=Array[UInt64]()))
        _box(app).value.padding.append(Bytes4096())
        assert _box(app).length > 4096, "expected box length >4096"

    @public
    def append(self, app: Application, value: Parent) -> None:
        _box(app).value.grand.arr.append(value)

    @public
    def pop(self, app: Application) -> Parent:
        return _box(app).value.grand.arr.pop()

    @public
    def nested_uint(self, app: Application, idx: UInt64) -> UInt64:
        return _box(app).value.grand.arr[idx].child.uint

    @public
    def nested_bool(self, app: Application, idx: UInt64) -> bool:
        return _box(app).value.grand.arr[idx].child.bool_

    @public
    def nested_arr_append(self, app: Application, item_idx: UInt64, value: UInt64) -> None:
        _box(app).value.items[item_idx].arr.append(value)

    @public
    def nested_arr_pop(self, app: Application, item_idx: UInt64) -> UInt64:
        return _box(app).value.items[item_idx].arr.pop()

    @public
    def dynamic_append(self, app: Application, item: ItemWithArray) -> None:
        _box(app).value.items.append(item.copy())

    @public
    def dynamic_pop(self, app: Application) -> ItemWithArray:
        return _box(app).value.items.pop()

    @public
    def clear_padding(self, app: Application) -> None:
        _discarded = _box(app).value.padding.pop()
