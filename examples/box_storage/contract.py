import typing

from algopy import Box, BoxMap, BoxRef, Bytes, Global, String, Txn, UInt64, arc4, subroutine

StaticInts: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[4]]


class BoxContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box_a = Box(UInt64)
        self.box_b = Box[Bytes](Bytes, key="b")
        self.box_c = Box(arc4.String, key=b"BOX_C")
        self.box_map = BoxMap(UInt64, String, key_prefix="")
        self.box_ref = BoxRef()

    @arc4.abimethod
    def set_boxes(self, a: UInt64, b: Bytes, c: arc4.String) -> None:
        self.box_a.value = a
        self.box_b.value = b
        self.box_c.value = c

        self.box_a.value += 3

        assert self.box_a.length == 8
        assert self.box_b.length == b.length
        assert self.box_c.length == c.bytes.length

    @arc4.abimethod
    def check_keys(self) -> None:
        assert self.box_a.key == b"box_a", "box a key ok"
        assert self.box_b.key == b"b", "box b key ok"
        assert self.box_c.key == b"BOX_C", "box c key ok"

    @arc4.abimethod
    def delete_boxes(self) -> None:
        del self.box_a.value
        del self.box_b.value
        del self.box_c.value
        assert self.box_a.get(default=UInt64(42)) == 42
        assert self.box_b.get(default=Bytes(b"42")) == b"42"
        assert self.box_c.get(default=arc4.String("42")) == "42"
        a, a_exists = self.box_a.maybe()
        assert not a_exists
        assert a == 0

    @arc4.abimethod
    def read_boxes(self) -> tuple[UInt64, Bytes, arc4.String]:
        return get_box_value_plus_1(self.box_a) - 1, self.box_b.value, self.box_c.value

    @arc4.abimethod
    def boxes_exist(self) -> tuple[bool, bool, bool]:
        return bool(self.box_a), bool(self.box_b), bool(self.box_c)

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
        assert self.box_map[key_0].bytes.length == value.bytes.length
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
