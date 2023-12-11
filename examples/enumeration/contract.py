from puyapy import Bytes, Contract, subroutine, UInt64, uenumerate, urange


class EnumerationContract(Contract):
    def approval_program(self) -> bool:
        iteration_count, item_sum, index_sum = enumerate_urange(UInt64(10), UInt64(21), UInt64(5))

        assert iteration_count == 6
        assert item_sum == 90
        assert index_sum == 3

        iteration_count, item_concat, index_sum = enumerate_tuple(
            (Bytes(b"How"), Bytes(b"Now"), Bytes(b"Brown"), Bytes(b"Cow"))
        )

        assert iteration_count == 8
        assert item_concat == Bytes(b"HowNowBrownCowHowNowBrownCow")
        assert index_sum == 6

        iteration_count, item_concat, index_sum = enumerate_bytes((Bytes(b"abcdefg")))

        assert iteration_count == 14
        assert item_concat == Bytes(b"abcdefgabcdefg")
        assert index_sum == 21

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def enumerate_urange(start: UInt64, stop: UInt64, step: UInt64) -> tuple[UInt64, UInt64, UInt64]:
    iteration_count = UInt64(0)
    item_sum = UInt64(0)
    index_sum = UInt64(0)

    for item in urange(start, stop, step):
        iteration_count += 1
        item_sum += item

    for index, item in uenumerate(urange(start, stop, step)):
        iteration_count += 1
        item_sum += item
        index_sum += index

    return iteration_count, item_sum, index_sum


@subroutine
def enumerate_tuple(tup: tuple[Bytes, Bytes, Bytes, Bytes]) -> tuple[UInt64, Bytes, UInt64]:
    iteration_count = UInt64(0)
    item_concat = Bytes(b"")
    index_sum = UInt64(0)

    for item in tup:
        iteration_count += 1
        item_concat += item
    for index, item in uenumerate(tup):
        iteration_count += 1
        item_concat += item
        index_sum += index

    return iteration_count, item_concat, index_sum


@subroutine
def enumerate_bytes(bytes: Bytes) -> tuple[UInt64, Bytes, UInt64]:
    iteration_count = UInt64(0)
    item_concat = Bytes(b"")
    index_sum = UInt64(0)

    for item in bytes:
        iteration_count += 1
        item_concat += item
    for index, item in uenumerate(bytes):
        iteration_count += 1
        item_concat += item
        index_sum += index

    return iteration_count, item_concat, index_sum
