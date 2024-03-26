from algopy import Contract, UInt64
from algopy.arc4 import (
    Byte,
    DynamicBytes,
    UInt8,
)


class Arc4DynamicBytesContract(Contract):
    def approval_program(self) -> bool:
        total = UInt64(0)
        dynamic_bytes = DynamicBytes(Byte(2), UInt8(3), 1)
        assert dynamic_bytes.native == b"\x02\x03\x01"
        assert dynamic_bytes.bytes == b"\x00\x03\x02\x03\x01"

        for uint8_item in dynamic_bytes:
            total += uint8_item.native

        assert total == 6, "Total should be of dynamic_bytes items"

        dynamic_bytes2 = DynamicBytes(b"\x03\x04")
        assert dynamic_bytes2.native == b"\x03\x04"
        assert dynamic_bytes2.bytes == b"\x00\x02\x03\x04"

        for uint8_item in dynamic_bytes2:
            total += uint8_item.native

        dynamic_bytes3 = DynamicBytes(dynamic_bytes2.native)
        assert dynamic_bytes3.native == b"\x03\x04"
        assert dynamic_bytes3.bytes == b"\x00\x02\x03\x04"

        for uint8_item in dynamic_bytes2:
            total += uint8_item.native

        assert total == 20, "Total should now include sum of dynamic_bytes3 items"
        return True

    def clear_state_program(self) -> bool:
        return True
