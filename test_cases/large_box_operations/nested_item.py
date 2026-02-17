import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, Struct, UInt64, public

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


class NestedItemArrayUInt64(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(StructWithNestedArray)

    @public
    def bootstrap(self) -> None:
        self.box.value = StructWithNestedArray(
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
        self.box.value.items.append(ItemWithArray(arr=Array[UInt64]()))
        self.box.value.padding.append(Bytes4096())
        assert self.box.length > 4096, "expected box length >4096"

    @public
    def append(self, value: Parent) -> None:
        self.box.value.grand.arr.append(value)

    @public
    def pop(self) -> Parent:
        return self.box.value.grand.arr.pop()

    @public
    def nested_uint(self, idx: UInt64) -> UInt64:
        return self.box.value.grand.arr[idx].child.uint

    @public
    def nested_bool(self, idx: UInt64) -> bool:
        return self.box.value.grand.arr[idx].child.bool_

    @public
    def nested_arr_append(self, item_idx: UInt64, value: UInt64) -> None:
        self.box.value.items[item_idx].arr.append(value)

    @public
    def nested_arr_pop(self, item_idx: UInt64) -> UInt64:
        return self.box.value.items[item_idx].arr.pop()

    @public
    def dynamic_append(self, item: ItemWithArray) -> None:
        self.box.value.items.append(item.copy())

    @public
    def dynamic_pop(self) -> ItemWithArray:
        return self.box.value.items.pop()

    @public
    def clear_padding(self) -> None:
        _discarded = self.box.value.padding.pop()
