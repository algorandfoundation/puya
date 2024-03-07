from puyapy import Contract, UInt64
from puyapy.arc4 import (
    Byte,
    DynamicBytes,
    UInt8,
)


class Arc4DynamicBytesContract(Contract):
    def approval_program(self) -> bool:
        total = UInt64(0)
        dynamic_bytes = DynamicBytes(Byte(2), UInt8(3))
        assert dynamic_bytes.decode() == b"\x02\x03"
        assert dynamic_bytes.bytes == b"\x00\x02\x02\x03"

        for uint8_item in dynamic_bytes:
            total += uint8_item.decode()

        assert total == 5, "Total should be of dynamic_bytes items"

        dynamic_bytes2 = DynamicBytes(b"\x03\x04")
        assert dynamic_bytes2.decode() == b"\x03\x04"
        assert dynamic_bytes2.bytes == b"\x00\x02\x03\x04"

        for uint8_item in dynamic_bytes2:
            total += uint8_item.decode()

        dynamic_bytes3 = DynamicBytes(dynamic_bytes2.decode())
        assert dynamic_bytes3.decode() == b"\x03\x04"
        assert dynamic_bytes3.bytes == b"\x00\x02\x03\x04"

        for uint8_item in dynamic_bytes2:
            total += uint8_item.decode()

        assert total == 19, "Total should now include sum of dynamic_bytes3 items"
        return True

    def clear_state_program(self) -> bool:
        return True
