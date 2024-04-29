import typing

from algopy import Box, BoxMap, BoxRef, Bytes, Global, String, Txn, UInt64, arc4

StaticInts: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[4]]


class BoxContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box_a = Box(UInt64, key=b"BOX_A")
        self.box_b = Box(Bytes, key=b"b")
        self.box_c = Box(arc4.String, key=b"BOX_C")
        self.box_map = BoxMap(UInt64, String)

    @arc4.abimethod
    def set_boxes(self, a: UInt64, b: Bytes, c: arc4.String) -> None:
        self.box_a.value = a
        self.box_b.value = b
        self.box_c.value = c

        self.box_a.value += 3

    @arc4.abimethod
    def read_boxes(self) -> tuple[UInt64, Bytes, arc4.String]:
        return self.box_a.value, self.box_b.value, self.box_c.value

    @arc4.abimethod
    def boxes_exist(self) -> tuple[bool, bool, bool]:
        return bool(self.box_a), bool(self.box_b), bool(self.box_c)

    @arc4.abimethod
    def slice_box(self) -> None:
        box_0 = Box(Bytes, key=b"0")
        box_0.value = Bytes(b"Testing testing 123")
        assert box_0.value[0:7] == b"Testing"

        self.box_c.value = arc4.String("Hello")
        assert self.box_c.value.bytes[2:10] == b"Hello"

    @arc4.abimethod
    def arc4_box(self) -> None:
        box_d = Box(StaticInts, key=b"d")
        box_d.value = StaticInts(arc4.UInt8(0), arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3))

        assert box_d.value[0] == 0
        assert box_d.value[1] == 1
        assert box_d.value[2] == 2
        assert box_d.value[3] == 3

    @arc4.abimethod
    def box_blob(self) -> None:
        box_blob = BoxRef(key=b"blob")
        sender_bytes = Txn.sender.bytes
        app_address = Global.current_application_address.bytes
        assert box_blob.create(size=8000)
        box_blob.replace(0, sender_bytes)
        box_blob.splice(0, 0, app_address)
        first_64 = box_blob.extract(0, 32 * 2)
        assert first_64 == app_address + sender_bytes
        assert box_blob.delete()

        value, exists = box_blob.maybe()
        assert not exists
        assert box_blob.get(default=sender_bytes) == sender_bytes
        box_blob.create(sender_bytes + app_address)
        assert box_blob, "Blob exists"
        assert box_blob.length == 64

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

    @arc4.abimethod
    def box_map_set(self, key: UInt64, value: String) -> None:
        self.box_map[key] = value

    @arc4.abimethod
    def box_map_get(self, key: UInt64) -> String:
        return self.box_map[key]

    @arc4.abimethod
    def box_map_exists(self, key: UInt64) -> bool:
        return key in self.box_map
