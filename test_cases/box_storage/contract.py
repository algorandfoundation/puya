from puyapy import arc4, UInt64, Bytes, Box, BoxMap


class BoxContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box_a = Box(UInt64, description="This is box a")
        self.box_b = Box(Bytes, description="This is box b", key=b"b")
        self.box_c = Box(arc4.String, description="This is box c")
        self.box_map = BoxMap(UInt64, Bytes, description="Map number to bytes", key_prefix=b"map_")

    @arc4.abimethod
    def set_boxes(self, a: UInt64, b: Bytes, c: arc4.String) -> None:
        self.box_a.value = a
        self.box_b.value = b
        self.box_c.value = c

    @arc4.abimethod
    def read_boxes(self) -> tuple[UInt64, Bytes, arc4.String]:
        return self.box_a.value, self.box_b.value, self.box_c.value

    @arc4.abimethod
    def boxes_exist(self) -> tuple[bool, bool, bool]:
        return bool(self.box_a), bool(self.box_b), bool(self.box_c)

    @arc4.abimethod
    def box_map_set(self, key: UInt64, value: Bytes) -> None:
        self.box_map[key] = value

    @arc4.abimethod
    def box_map_get(self, key: UInt64) -> Bytes:
        return self.box_map[key]

    @arc4.abimethod
    def box_map_exists(self, key: UInt64) -> bool:
        return key in self.box_map
