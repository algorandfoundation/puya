import typing

from algopy import (
    Account,
    BigUInt,
    Box,
    ImmutableArray,
    ReferenceArray,
    Txn,
    UInt64,
    arc4,
    op,
    subroutine,
    urange,
)


class More(arc4.Struct, frozen=True):
    foo: arc4.UInt64
    bar: arc4.UInt64


class Xtra(typing.NamedTuple):
    a: UInt64
    b: UInt64
    c: Account
    d: More
    e: BigUInt


class Point(typing.NamedTuple):
    x: arc4.UInt64
    y: UInt64
    other: Xtra


class StaticSizeContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod()
    def test_array(self, x1: arc4.UInt64, y1: UInt64, x2: arc4.UInt64, y2: UInt64) -> UInt64:
        self.count = UInt64(0)
        path = ReferenceArray(
            Point(x=arc4.UInt64(), y=UInt64(), other=self.xtra()),
            Point(x=x1, y=y1, other=self.xtra()),
            Point(x=x2, y=y2, other=self.xtra()),
        )
        for i in urange(3):
            assert path[i].other.b == i + 1
            assert path[i].other.d.foo == i + 2
            assert path[i].other.d.bar == (i + 1) * (i + 1)

        Box(ImmutableArray[Point], key="a").value = path.freeze()
        return path_length(path)

    @arc4.abimethod()
    def test_extend_from_tuple(self, some_more: tuple[More, More]) -> ImmutableArray[More]:
        arr = ReferenceArray[More]()
        arr.extend(some_more)
        last = arr[-1]
        assert last == some_more[1]
        result = arr.freeze()
        assert result[-1] == last
        return result

    @arc4.abimethod()
    def test_extend_from_arc4_tuple(
        self, some_more: arc4.Tuple[More, More]
    ) -> ImmutableArray[More]:
        arr = ReferenceArray[More]()
        arr.extend(some_more)
        return arr.freeze()

    @arc4.abimethod()
    def test_bool_array(self, length: UInt64) -> UInt64:
        arr = ReferenceArray[bool]()
        assert arr.length == 0

        for i in urange(1, length + 1):
            arr.append(i % 2 == 0)
        assert arr.length == length, "expected correct length"

        arr2 = arr.copy()
        arr2.extend(arr)
        assert arr2.length == length * 2, "expected correct length"

        count = UInt64(0)
        for val in arr:
            if val:
                count += 1
        return count

    @arc4.abimethod()
    def test_arc4_conversion(self, length: UInt64) -> arc4.DynamicArray[arc4.UInt64]:
        arr = ReferenceArray[arc4.UInt64]()
        assert arr.length == 0

        for i in urange(1, length + 1):
            arr.append(arc4.UInt64(i))
        assert arr.length == length, "expected correct length"
        count = UInt64(0)
        for val in arr:
            if val:
                count += 1

        arc4_arr = arc4.DynamicArray[arc4.UInt64]()
        arc4_arr.extend(arr)

        return arc4_arr

    @arc4.abimethod()
    def sum_array(self, arc4_arr: arc4.DynamicArray[arc4.UInt64]) -> UInt64:
        arr = ReferenceArray[arc4.UInt64]()
        arr.extend(arc4_arr)

        total = UInt64(0)
        for item in arr:
            total += item.native

        return total

    @subroutine
    def xtra(self) -> Xtra:
        self.count += 1
        return Xtra(
            a=Txn.num_app_args,
            b=self.count,
            c=Txn.sender,
            d=self.more(),
            e=BigUInt(self.count),
        )

    @subroutine(inline=False)
    def more(self) -> More:
        return More(foo=arc4.UInt64(self.count + 1), bar=arc4.UInt64(self.count * self.count))

    @arc4.abimethod()
    def test_arc4_bool(self) -> ImmutableArray[arc4.Bool]:
        arr = ReferenceArray[arc4.Bool]()
        arr.append(arc4.Bool(Txn.sender == Txn.receiver))
        arr.append(arc4.Bool(Txn.sender != Txn.receiver))

        dyn_arr = arc4.DynamicArray[arc4.Bool]()
        dyn_arr.extend(arr)
        assert dyn_arr.length == 2, "expected correct length"
        assert dyn_arr.bytes.length == 3, "expected 3 bytes"
        assert dyn_arr[0] == (Txn.sender == Txn.receiver), "expected correct value at 0"
        assert dyn_arr[1] == (Txn.sender != Txn.receiver), "expected correct value at 1"

        arr2 = arr.copy()
        # note: not supported currently
        # arr2.extend(dyn_array)
        for b in dyn_arr:
            arr2.append(b)
        assert arr2.length == 4, "expected correct length"
        assert arr2[0] == (Txn.sender == Txn.receiver), "expected correct value at 0"
        assert arr2[1] == (Txn.sender != Txn.receiver), "expected correct value at 1"
        assert arr2[2] == (Txn.sender == Txn.receiver), "expected correct value at 2"
        assert arr2[3] == (Txn.sender != Txn.receiver), "expected correct value at 3"

        return arr.freeze()


@subroutine
def path_length(path: ReferenceArray[Point]) -> UInt64:
    last_point = path[0]
    length = UInt64()
    for point_idx in urange(1, path.length):
        point = path[point_idx]
        if point.x < last_point.x:
            dx = last_point.x.native - point.x.native
        else:
            dx = point.x.native - last_point.x.native
        if point.y < last_point.y:
            dy = last_point.y - point.y
        else:
            dy = point.y - last_point.y
        length += op.sqrt(dx * dx + dy * dy)
    return length
