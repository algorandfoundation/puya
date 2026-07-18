import typing

from algopy import (
    ARC4Contract,
    Array,
    Box,
    BoxMap,
    Bytes,
    Global,
    String,
    Struct,
    Txn,
    UInt64,
    arc4,
    subroutine,
    urange,
)

StaticInts: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[4]]


# example: INIT_BOX_STORAGE_STRUCT
class UserStruct(arc4.Struct):
    """An ARC-4 struct stored as the value type of a BoxMap."""

    name: arc4.String
    id: arc4.UInt64
    asset: arc4.UInt64


# example: INIT_BOX_STORAGE_STRUCT


class InnerStruct(Struct):
    """A nested algopy Struct with a dynamic array inside it."""

    c: UInt64
    arr: Array[UInt64]
    d: UInt64


class NestedStruct(Struct):
    """Composition of Structs, including an Array of Structs."""

    a: UInt64
    inner: InnerStruct
    siblings: Array[InnerStruct]
    b: UInt64


class BoxStorage(ARC4Contract):
    # example: INIT_BOX_STORAGE
    def __init__(self) -> None:
        # Box[T] holds a single value of type T. The key defaults to the attribute name.
        self.box_int = Box(UInt64)
        # An explicit `key` overrides the attribute-derived default.
        self.box_dynamic_bytes = Box(arc4.DynamicBytes, key="b")
        self.box_string = Box(arc4.String, key=b"BOX_STRING")
        self.box_bytes = Box(Bytes, key=b"BOX_BYTES")
        # BoxMap[K, V] is a family of boxes keyed by K with values of type V.
        self.box_map = BoxMap(UInt64, String, key_prefix="")
        # A BoxMap whose value is a Struct.
        self.box_map_struct = BoxMap(arc4.UInt64, UserStruct, key_prefix="users")
        # Boxes can also hold a non-ARC-4 Struct, including nested ones with
        # dynamic arrays inside.
        self.box_nested = Box(NestedStruct)

    # example: INIT_BOX_STORAGE

    # example: GET_BOX_STORAGE
    @arc4.abimethod
    def get_box(self) -> UInt64:
        # `.value` reads the current contents; fails if the box does not exist.
        return self.box_int.value

    @arc4.abimethod
    def get_item_box_map(self, key: UInt64) -> String:
        # Indexing reads the box for `key`; fails if it does not exist.
        return self.box_map[key]

    @arc4.abimethod
    def get_box_map(self) -> String:
        # `.get(key, default=...)` returns the default when the box does not exist.
        return self.box_map.get(UInt64(1), default=String("default"))

    @arc4.abimethod
    def maybe_box(self) -> tuple[UInt64, bool]:
        # `.maybe()` returns `(value, exists)`; `value` is undefined when False.
        return self.box_int.maybe()

    @arc4.abimethod
    def maybe_box_map(self) -> tuple[String, bool]:
        value, exists = self.box_map.maybe(UInt64(1))
        if not exists:
            value = String("")
        return value, exists

    # example: GET_BOX_STORAGE

    # example: GET_BOX_STORAGE_EXAMPLE
    @arc4.abimethod
    def get_box_example(self) -> tuple[UInt64, Bytes, arc4.String]:
        return (
            self.box_int.value,
            self.box_dynamic_bytes.value.native,
            self.box_string.value,
        )

    @arc4.abimethod
    def get_box_map_struct(self, key: arc4.UInt64) -> UserStruct:
        return self.box_map_struct[key]

    @arc4.abimethod
    def read_box_passed_to_subroutine(self, key: UInt64) -> String:
        # Box and BoxMap proxies can be passed to subroutines.
        return get_box_map_value_from_key_plus_1(self.box_map, key)

    # example: GET_BOX_STORAGE_EXAMPLE

    # example: SET_BOX_STORAGE
    @arc4.abimethod
    def set_box(self, value: UInt64) -> None:
        self.box_int.value = value

    @arc4.abimethod
    def set_box_map(self, key: UInt64, value: String) -> None:
        self.box_map[key] = value

    @arc4.abimethod
    def set_box_map_struct(self, key: arc4.UInt64, value: UserStruct) -> bool:
        # ARC-4 Structs are reference-like; `.copy()` is required when assigning
        # to storage so the box owns its own bytes.
        self.box_map_struct[key] = value.copy()
        assert self.box_map_struct[key] == value, "stored struct must round-trip"
        return True

    # example: SET_BOX_STORAGE

    # example: SET_BOX_STORAGE_EXAMPLE
    @arc4.abimethod
    def set_box_example(
        self,
        value_int: UInt64,
        value_dbytes: arc4.DynamicBytes,
        value_string: arc4.String,
    ) -> None:
        self.box_int.value = value_int
        self.box_dynamic_bytes.value = value_dbytes.copy()
        self.box_string.value = value_string
        self.box_bytes.value = value_dbytes.native

        # Boxes support in-place mutation via augmented assignment.
        self.box_int.value += 3

    # example: SET_BOX_STORAGE_EXAMPLE

    # example: DELETE_BOX_STORAGE
    @arc4.abimethod
    def delete_box(self) -> None:
        # `del box.value` removes the box entirely.
        del self.box_int.value
        del self.box_dynamic_bytes.value
        del self.box_string.value

        # After deletion, `.get(default=...)` returns the default.
        assert self.box_int.get(default=UInt64(42)) == 42, "box_int must be deleted"
        assert (
            self.box_dynamic_bytes.get(default=arc4.DynamicBytes(b"42")).native == b"42"
        ), "box_dynamic_bytes must be deleted"
        assert self.box_string.get(default=arc4.String("42")) == "42", "box_string must be deleted"

    @arc4.abimethod
    def delete_box_map(self, key: UInt64) -> None:
        del self.box_map[key]

    # example: DELETE_BOX_STORAGE

    # example: LENGTH_BOX_STORAGE
    @arc4.abimethod
    def box_int_length(self) -> UInt64:
        # `.length` is the size in bytes of the stored value.
        return self.box_int.length

    @arc4.abimethod
    def box_map_length(self, key: UInt64) -> UInt64:
        if key not in self.box_map:
            return UInt64(0)
        return self.box_map.length(key)

    @arc4.abimethod
    def box_map_struct_length(self) -> bool:
        key = arc4.UInt64(0)
        value = UserStruct(name=arc4.String("testName"), id=arc4.UInt64(70), asset=arc4.UInt64(2))

        self.box_map_struct[key] = value.copy()
        # The on-chain length matches the encoded byte length of the struct.
        assert (
            self.box_map_struct[key].bytes.length == value.bytes.length
        ), "stored struct must have the same encoded length"
        assert (
            self.box_map_struct.length(key) == value.bytes.length
        ), "box length must match the encoded length"
        return True

    # example: LENGTH_BOX_STORAGE

    # example: EXTRACT_BOX
    @arc4.abimethod
    def extract_box(self) -> None:
        # An ad-hoc Box[Bytes] is useful for low-level byte slicing.
        box = Box(Bytes, key=String("blob"))
        # `.create(size=n)` allocates a zero-filled box; True means newly created.
        assert box.create(size=UInt64(32)), "box must not exist yet"

        # Addresses are 32 bytes long.
        sender_bytes = Txn.sender.bytes
        app_address = Global.current_application_address.bytes
        value_3 = Bytes(b"hello")
        # `.replace(offset, value)` overwrites bytes in place.
        box.replace(0, sender_bytes)
        # `.resize(size)` grows (zero-padding the end) or shrinks the box;
        # `.splice` cannot grow a box, so resize first to make room.
        box.resize(32 * 2 + value_3.length)
        # `.splice(offset, drop, value)` shifts bytes within the fixed-size
        # box: here it inserts `app_address` at the front, pushing the
        # existing content right; bytes past the box length are dropped.
        box.splice(0, 0, app_address)
        box.replace(64, value_3)
        # `.extract(offset, length)` returns a slice without mutation.
        prefix = box.extract(0, 32 * 2 + value_3.length)
        assert prefix == app_address + sender_bytes + value_3, "unexpected box contents"
        del box.value

    # example: EXTRACT_BOX

    # example: OTHER_OPS_BOX
    @arc4.abimethod
    def exist_box(self) -> tuple[bool, bool, bool, bool]:
        # `bool(box)` is True if the box exists.
        return (
            bool(self.box_int),
            bool(self.box_dynamic_bytes),
            bool(self.box_string),
            bool(self.box_bytes),
        )

    @arc4.abimethod
    def slice_box(self) -> None:
        box_0 = Box(Bytes, key=String("scratch"))
        box_0.value = Bytes(b"Testing testing 123")
        assert box_0.value[0:7] == b"Testing", "box value must support slicing"

        self.box_string.value = arc4.String("Hello")
        # `.value.bytes` exposes the raw encoded bytes of an ARC-4 value
        # (an arc4.String is prefixed with its 2-byte length).
        assert self.box_string.value.bytes[2:10] == b"Hello", "unexpected string contents"
        del box_0.value

    @arc4.abimethod
    def arc4_box(self) -> None:
        box_d = Box(StaticInts, key=Bytes(b"d"))
        box_d.value = StaticInts(arc4.UInt8(0), arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3))

        assert box_d.value[0] == 0, "first element must be 0"
        assert box_d.value[3] == 3, "last element must be 3"
        del box_d.value

    @arc4.abimethod
    def key_box(self) -> Bytes:
        return self.box_int.key

    @arc4.abimethod
    def key_box_example(self) -> None:
        assert self.box_dynamic_bytes.key == b"b", "key must match the explicit str key"
        assert self.box_string.key == b"BOX_STRING", "key must match the explicit bytes key"
        assert self.box_bytes.key == b"BOX_BYTES", "key must match the explicit bytes key"

    # example: OTHER_OPS_BOX

    # example: OTHER_OPS_BOX_MAP
    @arc4.abimethod
    def box_map_exists(self, key: UInt64) -> bool:
        # `key in box_map` is True if the box for `key` exists.
        return key in self.box_map

    @arc4.abimethod
    def box_map_struct_exists(self, key: arc4.UInt64) -> bool:
        return key in self.box_map_struct

    @arc4.abimethod
    def key_prefix_box_map(self) -> Bytes:
        return self.box_map.key_prefix

    # example: OTHER_OPS_BOX_MAP

    # example: NESTED_STRUCT_BOX
    @arc4.abimethod
    def nested_struct_write(self, value: UInt64) -> None:
        # Boxes can hold Structs whose fields are themselves Structs or Arrays.
        # Field assignment writes through to the underlying box bytes.
        self.box_nested.value = NestedStruct(
            a=value,
            inner=InnerStruct(c=value + 1, arr=Array[UInt64](), d=value + 2),
            siblings=Array[InnerStruct](),
            b=value + 3,
        )
        for i in urange(3):
            self.box_nested.value.inner.arr.append(i)

    @arc4.abimethod
    def nested_struct_sum(self) -> UInt64:
        total = self.box_nested.value.a + self.box_nested.value.b
        total += self.box_nested.value.inner.c + self.box_nested.value.inner.d
        for v in self.box_nested.value.inner.arr:
            total += v
        return total

    # example: NESTED_STRUCT_BOX


@subroutine
def get_box_map_value_from_key_plus_1(box_map: BoxMap[UInt64, String], key: UInt64) -> String:
    """BoxMap proxies are first-class values and can be passed to subroutines."""
    return box_map[key + 1]
