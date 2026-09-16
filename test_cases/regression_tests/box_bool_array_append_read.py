from algopy import (
    ARC4Contract,
    Box,
    OpUpFeeSource,
    ReferenceArray,
    UInt64,
    arc4,
    ensure_budget,
    urange,
)

BoolArray = arc4.DynamicArray[arc4.Bool]


class BoxBoolArrayAppendRead(ARC4Contract):
    """Regression test: appending to a dynamic array of bools stored in a box was lowered
    to an in-place helper that advanced one byte per element, while reads of the same
    array are (correctly) bit packed. After two appends the box contained
    `[len=2][0x80][0x80]` and reading index 1 returned the (zero) bit 1 of the first byte,
    so `push(true); push(true)` read back as `[true, false]`."""

    def __init__(self) -> None:
        self.boxed = Box(BoolArray)

    @arc4.abimethod
    def box_push_read(self) -> bool:
        self.boxed.value = BoolArray()
        self.boxed.value.append(arc4.Bool(True))
        self.boxed.value.append(arc4.Bool(True))
        return bool(self.boxed.value[0]) and bool(self.boxed.value[1])

    @arc4.abimethod
    def box_round_trip(self, n: UInt64) -> None:
        ensure_budget(UInt64(40_000), fee_source=OpUpFeeSource.GroupCredit)
        self.boxed.value = BoolArray()
        # append one at a time, crossing byte boundaries
        for i in urange(n):
            self.boxed.value.append(arc4.Bool(i % 3 == 0))
        assert self.boxed.value.length == n, "unexpected length after appends"
        assert self.boxed.length == 2 + (n + 7) // 8, "unexpected box size after appends"
        for i in urange(n):
            assert bool(self.boxed.value[i]) == (i % 3 == 0), "unexpected value after appends"

        # write every index, then read each back
        for i in urange(n):
            self.boxed.value[i] = arc4.Bool(i % 2 == 0)
        for i in urange(n):
            assert bool(self.boxed.value[i]) == (i % 2 == 0), "unexpected value after writes"

        # extend with an already bit packed array
        self.boxed.value.extend(BoolArray(arc4.Bool(True), arc4.Bool(False), arc4.Bool(True)))
        assert self.boxed.value.length == n + 3, "unexpected length after extend"
        assert (
            self.boxed.value[n] and not self.boxed.value[n + 1] and self.boxed.value[n + 2]
        ), "unexpected value after extend"

        # extend with a reference array, whose items are each encoded as a whole byte
        # rather than bit packed
        self.boxed.value.extend(ReferenceArray[arc4.Bool]((arc4.Bool(False), arc4.Bool(True))))
        assert self.boxed.value.length == n + 5, "unexpected length after reference array extend"
        assert (
            not self.boxed.value[n + 3] and self.boxed.value[n + 4]
        ), "unexpected value after reference array extend"

    @arc4.abimethod
    def box_access(self, index: UInt64, write: arc4.Bool) -> bool:
        if write.native:
            self.boxed.value[index] = write
            return True
        return self.boxed.value[index].native
