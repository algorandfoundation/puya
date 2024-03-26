from algopy import Contract, String, arc4

HELLO_WORLD = b"Hello World!"


class Arc4StringTypesContract(Contract):
    def approval_program(self) -> bool:
        some_bytes_as_string = arc4.String(String.from_bytes(HELLO_WORLD))

        some_bytes_as_bytes_again = some_bytes_as_string.native.bytes

        assert (
            some_bytes_as_string.bytes != HELLO_WORLD
        ), "Original bytes should not match encoded bytes"

        assert (
            some_bytes_as_string.bytes[2:] == HELLO_WORLD
        ), "Original bytes should match encoded if we strip the length header"

        assert some_bytes_as_bytes_again == HELLO_WORLD

        hello = arc4.String("Hello")
        space = arc4.String(" ")
        world = arc4.String("World!")

        assert arc4.String("Hello World!") == (hello + space + world)

        thing = arc4.String("hi")
        thing += thing
        assert thing == arc4.String("hihi")

        value = arc4.String("a") + arc4.String("b") + "cd"
        value += "e"
        value += arc4.String("f")
        value += arc4.String("g")
        assert arc4.String("abcdefg") == value
        return True

    def clear_state_program(self) -> bool:
        return True
