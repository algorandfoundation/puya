import typing

from algopy import (
    Array,
    Box,
    BoxMap,
    BoxRef,
    Bytes,
    FixedArray,
    Global,
    ImmutableFixedArray,
    String,
    Struct,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    op,
    size_of,
    subroutine,
    urange,
)

StaticInts: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[4]]
Bytes1024 = ImmutableFixedArray[arc4.Byte, typing.Literal[1024]]
ManyInts = FixedArray[UInt64, typing.Literal[513]]


class LargeStruct(Struct):
    a: Bytes1024
    b: Bytes1024
    c: Bytes1024
    d: Bytes1024
    e: UInt64
    f: Bytes1024
    g: Bytes1024
    h: UInt64


class FixedArrayUInt64(Struct):
    length: arc4.UInt16
    arr: FixedArray[UInt64, typing.Literal[4095]]


class DynamicArrayInAStruct(Struct):
    a: UInt64
    arr: Array[UInt64]
    b: UInt64
    arr2: Array[UInt64]


class FixedArrayInAStruct(Struct):
    a: UInt64
    arr_offset: arc4.UInt16
    b: UInt64
    arr2_offset: arc4.UInt16
    arr: FixedArrayUInt64
    # arr2 excluded as it is cannot be aligned correctly statically, without knowing
    # arr2_offset


class InnerStruct(Struct):
    c: UInt64
    arr_arr: Array[Array[UInt64]]
    d: UInt64


class NestedStruct(Struct):
    a: UInt64
    inner: InnerStruct
    woah: Array[InnerStruct]
    b: UInt64


class LargeNestedStruct(Struct):
    padding: FixedArray[arc4.Byte, typing.Literal[4096]]
    nested: NestedStruct


class BoxContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box_a = Box(UInt64)
        self.box_b = Box[arc4.DynamicBytes](arc4.DynamicBytes, key="b")
        self.box_c = Box(arc4.String, key=b"BOX_C")
        self.box_d = Box(Bytes)
        self.box_map = BoxMap(UInt64, String, key_prefix="")
        self.box_ref = BoxRef()
        self.box_large = Box(LargeStruct)
        self.many_ints = Box(ManyInts)
        assert size_of(ManyInts) > 4096, "expected ManyInts to exceed max bytes size"
        self.dynamic_box = Box(Array[UInt64])
        self.dynamic_arr_struct = Box(DynamicArrayInAStruct)
        self.too_many_bools = Box(FixedArray[bool, typing.Literal[33_000]])

    @arc4.abimethod
    def set_boxes(self, a: UInt64, b: arc4.DynamicBytes, c: arc4.String) -> None:
        self.box_a.value = a
        self.box_b.value = b.copy()
        self.box_c.value = c
        self.box_d.value = b.native
        self.box_large.create()
        self.box_large.value.e = UInt64(42)
        self.box_large.ref.replace(size_of(Bytes1024) * 4, arc4.UInt64(42).bytes)

        b_value = self.box_b.value.copy()
        assert self.box_b.value.length == b_value.length, "direct reference should match copy"

        self.box_a.value += 3

        # test .length
        assert self.box_a.length == 8
        assert self.box_b.length == b.bytes.length
        assert self.box_c.length == c.bytes.length
        assert self.box_d.length == b.native.length

        # test .value.bytes
        assert self.box_c.value.bytes[0] == c.bytes[0]
        assert self.box_c.value.bytes[-1] == c.bytes[-1]
        assert self.box_c.value.bytes[:-1] == c.bytes[:-1]
        assert self.box_c.value.bytes[:2] == c.bytes[:2]

        # test .value with Bytes type
        assert self.box_d.value[0] == b.native[0]
        assert self.box_d.value[-1] == b.native[-1]
        assert self.box_d.value[:-1] == b.native[:-1]
        assert self.box_d.value[:5] == b.native[:5]
        assert self.box_d.value[: UInt64(2)] == b.native[: UInt64(2)]

        assert self.box_large.length == size_of(LargeStruct)

    @arc4.abimethod
    def check_keys(self) -> None:
        assert self.box_a.key == b"box_a", "box a key ok"
        assert self.box_b.key == b"b", "box b key ok"
        assert self.box_c.key == b"BOX_C", "box c key ok"
        assert self.box_large.key == b"box_large", "box large key ok"

    @arc4.abimethod()
    def create_many_ints(self) -> None:
        self.many_ints.create()

    @arc4.abimethod()
    def set_many_ints(self, index: UInt64, value: UInt64) -> None:
        self.many_ints.value[index] = value

    @arc4.abimethod()
    def sum_many_ints(self) -> UInt64:
        ensure_budget(10_500)
        total = UInt64(0)
        for val in self.many_ints.value:
            total = total + val
        return total

    @arc4.abimethod
    def delete_boxes(self) -> None:
        del self.box_a.value
        del self.box_b.value
        del self.box_c.value
        assert self.box_a.get(default=UInt64(42)) == 42
        assert self.box_b.get(default=arc4.DynamicBytes(b"42")).native == b"42"
        assert self.box_c.get(default=arc4.String("42")) == "42"
        a, a_exists = self.box_a.maybe()
        assert not a_exists
        assert a == 0
        del self.box_large.value

    @arc4.abimethod()
    def indirect_extract_and_replace(self) -> None:
        large = self.box_large.value.copy()
        large.e += 1
        self.box_large.value = large.copy()

    @arc4.abimethod
    def read_boxes(self) -> tuple[UInt64, Bytes, arc4.String, UInt64]:
        return (
            get_box_value_plus_1(self.box_a) - 1,
            self.box_b.value.native,
            self.box_c.value,
            self.box_large.value.e,
        )

    @arc4.abimethod
    def boxes_exist(self) -> tuple[bool, bool, bool, bool]:
        return bool(self.box_a), bool(self.box_b), bool(self.box_c), bool(self.box_large)

    @arc4.abimethod
    def create_dynamic_arr_struct(self) -> None:
        self.dynamic_arr_struct.value = DynamicArrayInAStruct(
            a=Txn.num_app_args,
            arr=Array[UInt64](),
            b=Txn.num_app_args * 2,
            arr2=Array[UInt64](),
        )

    @arc4.abimethod
    def delete_dynamic_arr_struct(self) -> None:
        del self.dynamic_arr_struct.value

    @arc4.abimethod
    def append_dynamic_arr_struct(self, times: UInt64) -> UInt64:
        # TODO: support append using high level array operations, instead of
        #       relying on struct layout tricks with FixedArrayInAStruct
        assert self.dynamic_arr_struct.value.b == 2, "expected 2"
        arr_len = self.dynamic_arr_struct.value.arr.length
        arr2_len = self.dynamic_arr_struct.value.arr2.length

        # expand box
        self.dynamic_arr_struct.ref.resize(
            get_dynamic_arr2_struct_byte_index(arr_len + times, arr2_len)
        )
        # splice in zero bytes so existing data is in correct location
        self.dynamic_arr_struct.ref.splice(
            get_dynamic_arr_struct_byte_index(arr_len), 0, op.bzero(times * size_of(UInt64))
        )
        # update using a box typed as a FixedArray
        box = Box(FixedArrayInAStruct, key=self.dynamic_arr_struct.key)
        for i in urange(times):
            box.value.arr.arr[arr_len] = i
            arr_len += 1
        box.value.arr.length = arc4.UInt16(arr_len)
        # when calculating arr2_offset need to sub 2 from 0th index to account for length bytes
        arr2_offset = get_dynamic_arr2_struct_byte_index(arr_len, UInt64(0)) - 2
        box.value.arr2_offset = arc4.UInt16(arr2_offset)

        assert (
            self.dynamic_arr_struct.value.arr.length == arr_len
        ), "expected arr length to be correct"
        assert self.dynamic_arr_struct.value.arr2.length == 0, "expected arr2 length to be correct"
        return self.dynamic_arr_struct.value.arr.length

    @arc4.abimethod
    def pop_dynamic_arr_struct(self, times: UInt64) -> UInt64:
        # TODO: support pop using high level array operations, instead of
        #       relying on struct layout tricks with FixedArrayInAStruct

        arr_len = self.dynamic_arr_struct.value.arr.length - times
        arr2_len = self.dynamic_arr_struct.value.arr2.length
        # resize array
        box = Box(FixedArrayInAStruct, key=self.dynamic_arr_struct.key)
        arr2_offset = get_dynamic_arr2_struct_byte_index(arr_len, UInt64(0)) - 2
        box.value.arr.length = arc4.UInt16(arr_len)
        box.value.arr2_offset = arc4.UInt16(arr2_offset)
        index = get_dynamic_arr_struct_byte_index(arr_len)
        box.ref.splice(index, times * size_of(UInt64), b"")
        # truncate box
        # Note: this is currently the same as index, but could be different if there
        #       were multiple dynamic arrays
        size = get_dynamic_arr2_struct_byte_index(arr_len, arr2_len)
        self.dynamic_arr_struct.ref.resize(size)

        return self.dynamic_arr_struct.value.arr.length

    @arc4.abimethod()
    def set_nested_struct(self, struct: NestedStruct) -> None:
        box = Box(LargeNestedStruct, key="box")
        assert struct.a, "struct.a is truthy"
        struct_bytes = Txn.application_args(1)
        struct_size = struct_bytes.length
        tail_offset = UInt64(4096 + 2)
        # initialize box to zero
        box.create(size=tail_offset + struct_size)
        # set correct offset for dynamic portion
        box.ref.replace(tail_offset - 2, arc4.UInt16(tail_offset).bytes)
        # set dynamic data
        box.ref.replace(tail_offset, struct_bytes)

    @arc4.abimethod()
    def nested_write(self, index: UInt64, value: UInt64) -> None:
        box = Box(LargeNestedStruct, key="box")
        box.value.nested.a = value
        box.value.nested.b = value + 1
        box.value.nested.inner.arr_arr[index][index] = value + 2
        box.value.nested.inner.c = value + 3
        box.value.nested.inner.d = value + 4
        box.value.nested.woah[index].arr_arr[index][index] = value + 5

    @arc4.abimethod()
    def nested_read(self, i1: UInt64, i2: UInt64, i3: UInt64) -> UInt64:
        box = Box(LargeNestedStruct, key="box")
        a = box.value.nested.a
        b = box.value.nested.b
        arr_arr = box.value.nested.inner.arr_arr[i1][i2]
        c = box.value.nested.inner.c
        d = box.value.nested.inner.d
        woah_arr_arr = box.value.nested.woah[i1].arr_arr[i2][i3]

        return a + b + arr_arr + c + d + woah_arr_arr

    @arc4.abimethod
    def sum_dynamic_arr_struct(self) -> UInt64:
        assert self.dynamic_arr_struct.value.a == 1, "expected 1"
        assert self.dynamic_arr_struct.value.b == 2, "expected 2"
        total = self.dynamic_arr_struct.value.a + self.dynamic_arr_struct.value.b
        for val in self.dynamic_arr_struct.value.arr:
            total += val
        for val in self.dynamic_arr_struct.value.arr2:
            total += val
        return total

    @arc4.abimethod
    def create_bools(self) -> None:
        self.too_many_bools.create()

    @arc4.abimethod
    def set_bool(self, index: UInt64, value: bool) -> None:
        self.too_many_bools.value[index] = value

    @arc4.abimethod()
    def sum_bools(self, stop_at_total: UInt64) -> UInt64:
        total = UInt64()
        for value in self.too_many_bools.value:
            if value:
                total += 1
            if total == stop_at_total:
                break
        return total

    @arc4.abimethod
    def create_dynamic_box(self) -> None:
        self.dynamic_box.value = Array[UInt64]()

    @arc4.abimethod
    def delete_dynamic_box(self) -> None:
        del self.dynamic_box.value

    @arc4.abimethod
    def append_dynamic_box(self, times: UInt64) -> UInt64:
        # TODO: support append using high level array operations

        box = Box(FixedArrayUInt64, key=self.dynamic_box.key)
        arr_len = box.value.length.as_uint64()

        self.dynamic_box.ref.resize(2 + (arr_len + times) * 8)
        for i in urange(times):
            box.value.arr[arr_len] = i
            arr_len += 1

        box.value.length = arc4.UInt16(arr_len)
        return self.dynamic_box.value.length

    @arc4.abimethod
    def pop_dynamic_box(self, times: UInt64) -> UInt64:
        # TODO: support pop using high level array operations

        box = Box(FixedArrayUInt64, key=self.dynamic_box.key)
        arr_len = box.value.length.as_uint64() - times
        box.value.length = arc4.UInt16(arr_len)
        self.dynamic_box.ref.resize(2 + arr_len * 8)

        return self.dynamic_box.value.length

    @arc4.abimethod
    def sum_dynamic_box(self) -> UInt64:
        total = UInt64()
        for val in self.dynamic_box.value:
            total += val
        return total

    @arc4.abimethod
    def write_dynamic_box(self, index: UInt64, value: UInt64) -> None:
        self.dynamic_box.value[index] = value

    @arc4.abimethod
    def write_dynamic_arr_struct(self, index: UInt64, value: UInt64) -> None:
        self.dynamic_arr_struct.value.arr[index] = value

    @arc4.abimethod
    def slice_box(self) -> None:
        box_0 = Box(Bytes, key=String("0"))
        box_0.value = Bytes(b"Testing testing 123")
        assert box_0.value[0:7] == b"Testing"

        self.box_c.value = arc4.String("Hello")
        assert self.box_c.value.bytes[2:10] == b"Hello"

    @arc4.abimethod
    def arc4_box(self) -> None:
        box_d = Box(StaticInts, key=Bytes(b"d"))
        box_d.value = StaticInts(arc4.UInt8(0), arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3))

        assert box_d.value[0] == 0
        assert box_d.value[1] == 1
        assert box_d.value[2] == 2
        assert box_d.value[3] == 3

    @arc4.abimethod
    def test_box_ref(self) -> None:
        # init ref, with valid key types
        box_ref = BoxRef(key="blob")
        assert not box_ref, "no data"
        box_ref = BoxRef(key=b"blob")
        assert not box_ref, "no data"
        box_ref = BoxRef(key=Bytes(b"blob"))
        assert not box_ref, "no data"
        box_ref = BoxRef(key=String("blob"))
        assert not box_ref, "no data"

        # create
        assert box_ref.create(size=32)
        assert box_ref, "has data"

        # manipulate data
        sender_bytes = Txn.sender.bytes
        app_address = Global.current_application_address.bytes
        value_3 = Bytes(b"hello")
        box_ref.replace(0, sender_bytes)
        box_ref.resize(8000)
        box_ref.splice(0, 0, app_address)
        box_ref.replace(64, value_3)
        prefix = box_ref.extract(0, 32 * 2 + value_3.length)
        assert prefix == app_address + sender_bytes + value_3

        # delete
        assert box_ref.delete()
        assert box_ref.key == b"blob"

        # query
        value, exists = box_ref.maybe()
        assert not exists
        assert value == b""
        assert box_ref.get(default=sender_bytes) == sender_bytes

        # update
        box_ref.put(sender_bytes + app_address)
        assert box_ref, "Blob exists"
        assert box_ref.length == 64
        assert get_box_ref_length(box_ref) == 64

        # instance box ref
        self.box_ref.create(size=UInt64(32))
        assert self.box_ref, "has data"
        self.box_ref.delete()

    @arc4.abimethod
    def box_map_test(self) -> None:
        key_0 = UInt64(0)
        key_1 = UInt64(1)
        value = String("Hmmmmm")
        self.box_map[key_0] = value
        box_0 = self.box_map.box(key_0)

        assert self.box_map[key_0].bytes.length == value.bytes.length
        assert self.box_map[key_0].bytes.length == box_0.length
        assert self.box_map.length(key_0) == value.bytes.length

        assert self.box_map.get(key_1, default=String("default")) == String("default")
        value, exists = self.box_map.maybe(key_1)
        assert not exists
        assert key_0 in self.box_map
        assert self.box_map.key_prefix == b""

        # test box map not assigned to the class and passed to subroutine
        tmp_box_map = BoxMap(UInt64, String, key_prefix=Bytes())
        tmp_box_map[key_1] = String("hello")
        assert get_box_map_value_from_key_plus_1(tmp_box_map, UInt64(0)) == "hello"
        del tmp_box_map[key_1]

    @arc4.abimethod
    def box_map_set(self, key: UInt64, value: String) -> None:
        self.box_map[key] = value

    @arc4.abimethod
    def box_map_get(self, key: UInt64) -> String:
        return self.box_map[key]

    @arc4.abimethod
    def box_map_del(self, key: UInt64) -> None:
        del self.box_map[key]

    @arc4.abimethod
    def box_map_exists(self, key: UInt64) -> bool:
        return key in self.box_map


@subroutine
def get_box_value_plus_1(box: Box[UInt64]) -> UInt64:
    return box.value + 1


@subroutine
def get_box_ref_length(ref: BoxRef) -> UInt64:
    return ref.length


@subroutine
def get_box_map_value_from_key_plus_1(box_map: BoxMap[UInt64, String], key: UInt64) -> String:
    return box_map[key + 1]


@subroutine(inline=True)
def get_dynamic_arr_struct_byte_index(index: UInt64) -> UInt64:
    head = size_of(UInt64) + size_of(arc4.UInt16) + size_of(UInt64) + size_of(arc4.UInt16)
    dyn_arr_index = size_of(arc4.UInt16) + index * size_of(UInt64)
    return head + dyn_arr_index


@subroutine(inline=True)
def get_dynamic_arr2_struct_byte_index(arr_size: UInt64, arr2_index: UInt64) -> UInt64:
    head_and_dyn_arr = get_dynamic_arr_struct_byte_index(arr_size)
    dyn_arr2_index = size_of(arc4.UInt16) + arr2_index * size_of(UInt64)
    return head_and_dyn_arr + dyn_arr2_index
