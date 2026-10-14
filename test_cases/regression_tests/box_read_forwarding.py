from algopy import ARC4Contract, Box, Bytes, Txn, UInt64, arc4, subroutine, urange

UInt64Array = arc4.DynamicArray[arc4.UInt64]


class Inner(arc4.Struct):
    x: arc4.UInt64
    arr: UInt64Array


class BoxReadForwarding(ARC4Contract):
    """
    A value read from a box must not observe later modifications to that box.
    Cases restore any box they modify that a later case reads.
    """

    def __init__(self) -> None:
        self.b = Box(Bytes, key=b"b")
        self.a = Box(UInt64Array, key=b"a")
        self.d = Box(Inner, key=b"d")

    @arc4.abimethod
    def run_all(self) -> None:
        self.b.value = Bytes(b"abcd")
        self.a.value = UInt64Array(arc4.UInt64(1), arc4.UInt64(2))
        self.d.value = Inner(x=arc4.UInt64(1), arr=UInt64Array(arc4.UInt64(1), arc4.UInt64(2)))

        self.bytes_len_after_put()
        self.bytes_extract_after_splice()
        self.bytes_len_after_subroutine_write()
        self.bytes_len_after_conditional_put()
        self.bytes_len_in_loop_with_put()
        self.array_len_after_append()
        self.array_element_after_set()
        self.array_append_write_back_after_put()
        self.struct_array_replaced_with_other_array()

    @subroutine
    def bytes_len_after_put(self) -> None:
        m = self.b.value
        self.b.value = Bytes(b"\x05")
        assert m.length == 4
        self.b.value = Bytes(b"abcd")

    @subroutine
    def bytes_extract_after_splice(self) -> None:
        m = self.b.value
        self.b.splice(0, 1, b"qqq")
        assert m[0:2] == b"ab"
        self.b.value = Bytes(b"abcd")

    @subroutine
    def bytes_len_after_subroutine_write(self) -> None:
        m = self.b.value
        self.write_b()
        assert m.length == 4
        self.b.value = Bytes(b"abcd")

    @subroutine(inline=False)
    def write_b(self) -> None:
        self.b.value = Bytes(b"x")

    @subroutine
    def bytes_len_after_conditional_put(self) -> None:
        m = self.b.value
        if Txn.num_app_args:  # always true, but not known at compile time
            self.b.value = Bytes(b"x")
        assert m.length == 4
        self.b.value = Bytes(b"abcd")

    @subroutine
    def bytes_len_in_loop_with_put(self) -> None:
        m = self.b.value
        total = UInt64(0)
        for _i in urange(2):
            total += m.length
            self.b.value = Bytes(b"x")
        assert total == 8

    @subroutine
    def array_len_after_append(self) -> None:
        m = self.a.value.copy()
        self.a.value.append(arc4.UInt64(9))
        assert m.length == 2
        self.a.value = UInt64Array(arc4.UInt64(1), arc4.UInt64(2))

    @subroutine
    def array_element_after_set(self) -> None:
        m = self.a.value.copy()
        self.a.value[0] = arc4.UInt64(7)
        assert m[0] == 1
        self.a.value = UInt64Array(arc4.UInt64(1), arc4.UInt64(2))

    @subroutine
    def array_append_write_back_after_put(self) -> None:
        m = self.a.value.copy()
        self.a.value = UInt64Array(arc4.UInt64(7))
        m.append(arc4.UInt64(9))
        self.a.value = m.copy()
        assert self.a.value == UInt64Array(arc4.UInt64(1), arc4.UInt64(2), arc4.UInt64(9))

    @subroutine
    def struct_array_replaced_with_other_array(self) -> None:
        m = self.d.value.copy()
        other = UInt64Array(arc4.UInt64(5))
        other.append(arc4.UInt64(9))
        m.arr = other.copy()
        self.d.value = m.copy()
        assert self.d.value.arr == UInt64Array(arc4.UInt64(5), arc4.UInt64(9))
