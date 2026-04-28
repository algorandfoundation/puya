from algopy import Contract, UInt64, Bytes, Box


class WronglySizedBoxes(Contract):
    """
    Assigning to an incorrectly sized box should either succeed or fail during compilation
    """

    def approval_program(self) -> bool:
        bytes_box = Box(Bytes, key=b'bytes')
        assert bytes_box.create(size=UInt64(0))
        bytes_box.value = Bytes(b"test!")

        uint_box = Box(UInt64, key=b'uint')
        assert uint_box.create(size=UInt64(0))
        uint_box.value = UInt64(35)
        return True

    def clear_state_program(self) -> bool:
        return True
