from puyapy import Bytes, Contract
from puyapy.arc4 import (
    String,
)


class Arc4StringTypesContract(Contract):
    def approval_program(self) -> bool:
        some_bytes = Bytes(b"Hello World!")

        some_bytes_as_string = String.encode(some_bytes)

        some_bytes_as_bytes_again = some_bytes_as_string.decode()

        assert (
            some_bytes != some_bytes_as_string.bytes
        ), "Original bytes should not match encoded bytes"

        assert (
            some_bytes == some_bytes_as_string.bytes[2:]
        ), "Original bytes should match encoded if we strip the length header"

        assert some_bytes == some_bytes_as_bytes_again

        hello = String("Hello")
        space = String(" ")
        world = String("World!")

        assert String("Hello World!") == (hello + space + world)

        thing = String("hi")
        thing += thing
        assert thing == String("hihi")

        value = String("a") + String(Bytes(b"b")) + "cd"
        value += "e"
        value += String("f")
        value += String(Bytes(b"g"))
        assert String("abcdefg") == value
        return True

    def clear_state_program(self) -> bool:
        return True
