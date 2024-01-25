import typing

from puyapy import Bytes, Contract, arc4, uenumerate, urange, itob, UInt64, log


class MyContract(Contract):
    def approval_program(self) -> bool:
        # Check empty iterations don't error
        for i in reversed(urange(0)):
            log(itob(i))
        for x in reversed(arc4.StaticArray[arc4.UInt8, typing.Literal[0]]()):
            log(x.bytes)

        test_array = arc4.StaticArray(arc4.UInt8(0), arc4.UInt8(0), arc4.UInt8(0), arc4.UInt8(0))
        # urange: reversed items, forward index
        for index, item in uenumerate(reversed(urange(4))):
            test_array[index] = arc4.UInt8(item)
        assert test_array.bytes == Bytes.from_hex("03020100")

        # urange: forward items, reversed index
        for index, item in reversed(uenumerate(reversed(urange(4, 8)))):
            test_array[index] = arc4.UInt8(item)
            if index == 2:
                break
        assert test_array.bytes == Bytes.from_hex("03020504")

        # Indexable: Reversed items
        some_strings = arc4.StaticArray(arc4.String("a"), arc4.String("b"), arc4.String("c"))
        some_string_reversed = arc4.String("")
        for str_item in reversed(some_strings):
            some_string_reversed += str_item
        assert some_string_reversed == "cba"

        # Indexable: Reversed item and index
        bytes_reversed_with_index = Bytes(b"")
        for index, bytes_item in reversed(uenumerate(Bytes(b"HELLO"))):
            bytes_reversed_with_index += itob(index)[-1:] + bytes_item
        assert bytes_reversed_with_index == b"\04O\03L\02L\01E\00H"

        # Tuple: Reversed items, forward index
        for index, tuple_item in uenumerate(
            reversed(
                (
                    UInt64(0),
                    UInt64(1),
                    UInt64(2),
                    UInt64(3),
                )
            )
        ):
            assert index + tuple_item == 3

        # Tuple: Forward items, reverse index
        prev_item = UInt64(0)
        prev_index = UInt64(99)
        for index, tuple_item in reversed(
            uenumerate(
                reversed(
                    (
                        UInt64(5),
                        UInt64(6),
                        UInt64(7),
                        UInt64(8),
                    )
                )
            )
        ):
            assert prev_item < tuple_item
            assert prev_index > index
            assert index + tuple_item == 8

            prev_item = tuple_item
            prev_index = index

        return True

    def clear_state_program(self) -> bool:
        return True
