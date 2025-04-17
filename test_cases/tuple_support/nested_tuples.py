import typing

from algopy import (
    ARC4Contract,
    BoxMap,
    Bytes,
    ImmutableArray,
    String,
    UInt64,
    arc4,
    op,
    subroutine,
    urange,
)


class SimpleTup(typing.NamedTuple):
    a: UInt64
    b: UInt64


class Child(typing.NamedTuple):
    a: UInt64
    b: Bytes
    c: String


class Parent(typing.NamedTuple):
    foo: UInt64
    foo_arc: arc4.UInt64
    child: Child


class ParentWithList(typing.NamedTuple):
    parent: Parent
    children: ImmutableArray[Child]


class TupleWithMutable(typing.NamedTuple):
    arr: arc4.DynamicArray[arc4.UInt64]
    child: Child


class NestedTuples(ARC4Contract):
    def __init__(self) -> None:
        self.build_nested_call_count = UInt64(0)
        self.box = BoxMap(SimpleTup, SimpleTup)
        self.twm = TupleWithMutable(
            arr=arc4.DynamicArray[arc4.UInt64](),
            child=Child(
                a=UInt64(),
                b=Bytes(),
                c=String(),
            ),
        )

    @arc4.abimethod()
    def store_tuple(self, pwl: ParentWithList) -> None:
        self.pwl = pwl

    @arc4.abimethod()
    def load_tuple(self) -> ParentWithList:
        return self.pwl

    @arc4.abimethod()
    def store_tuple_in_box(self, key: SimpleTup) -> None:
        self.box[key] = key._replace(b=key.b + 1)

    @arc4.abimethod()
    def is_tuple_in_box(self, key: SimpleTup) -> bool:
        return key in self.box

    @arc4.abimethod()
    def load_tuple_from_box(self, key: SimpleTup) -> SimpleTup:
        return self.box[key]

    @arc4.abimethod()
    def mutate_local_tuple(self) -> TupleWithMutable:
        twm = TupleWithMutable(
            arr=arc4.DynamicArray(arc4.UInt64(0)),
            child=Child(
                a=UInt64(),
                b=Bytes(),
                c=String(),
            ),
        )
        twm[0].append(arc4.UInt64(1))
        twm.arr.append(arc4.UInt64(2))
        for i in urange(3):
            assert twm.arr[i] == i
        # TODO: support this?
        #       see below method for work around
        #       self.twm.arr.append(arc4.UInt64(1))
        return twm

    @arc4.abimethod()
    def mutate_tuple_in_storage_currently_supported_method(self) -> None:
        arr2 = self.twm.arr.copy()
        arr2.append(arc4.UInt64(1))
        self.twm = self.twm._replace(arr=arr2.copy())

    @arc4.abimethod()
    def run_tests(self) -> bool:
        x = (String("Hi"), String("There"))
        assert test_swap(x) == (String("There"), String("Hi"))
        y = (UInt64(1), x)
        z = (UInt64(0), UInt64(2), y)
        z2 = z[2]
        z2_1 = z2[1]
        _x, z2_1_1 = z2_1
        assert z2_1_1 == "There"

        (a, b, (c, d, (e,))) = test_rearrange(x[0], _b=x[1], args=z)
        assert (a, b) == (String("Hi"), UInt64(0))
        assert (c, d) == (UInt64(2), UInt64(1))
        assert e == String("There")

        test_intrinsics(UInt64(1), UInt64(2))
        test_nested_slicing()
        test_nested_singles(UInt64(1), reassign=True)
        test_nested_singles(UInt64(1), reassign=False)
        test_nested_mutation()

        assert z[2] == y

        test_nested_iteration()

        self.test_single_evaluation_nested()
        return True

    @arc4.abimethod()
    def nested_tuple_params(
        self, args: tuple[String, tuple[Bytes, tuple[UInt64]]]
    ) -> tuple[Bytes, tuple[String, UInt64]]:
        (s, (b, (u,))) = args
        return b, (s, u)

    @arc4.abimethod()
    def named_tuple(self, args: Child) -> Child:
        a, b, c = args
        return Child(a, b, c)

    @arc4.abimethod()
    def nested_named_tuple_params(self, args: Parent) -> Parent:
        foo, foo_arc, (a, b, c) = args
        return Parent(foo, foo_arc, Child(a, b, c))

    @subroutine
    def build_nested(self) -> tuple[tuple[String, UInt64], Bytes]:
        self.build_nested_call_count += 1
        return (String("hi"), UInt64(1)), Bytes(b"hmmm")

    @subroutine
    def test_single_evaluation_nested(self) -> None:
        self.build_nested_call_count = UInt64(0)
        result = self.build_nested() or self.build_nested()
        assert result[0][0] == "hi"
        assert self.build_nested_call_count == 1


@subroutine
def test_rearrange(
    _a: String, args: tuple[UInt64, UInt64, tuple[UInt64, tuple[String, String]]], _b: String
) -> tuple[String, UInt64, tuple[UInt64, UInt64, tuple[String]]]:
    (a, b, (c, (d, e))) = args

    return d, a, (b, c, (e,))


@subroutine
def test_swap(args: tuple[String, String]) -> tuple[String, String]:
    (a, b) = args
    return b, a


@subroutine
def test_intrinsics(num1: UInt64, num2: UInt64) -> None:
    nt = (UInt64(1), op.addw(num1, num2), UInt64(42))
    assert nt[0] == 1
    assert nt[-1] == 42
    assert nt[1] == (0, num1 + num2)  # type: ignore[comparison-overlap]
    assert nt[1][:1] == (0,)  # type: ignore[comparison-overlap]
    assert nt[1][1:] == (num1 + num2,)
    ((x, y),) = nt[1:2]
    assert x == 0
    assert y == num1 + num2


@subroutine
def test_nested_slicing() -> None:
    nt = (
        UInt64(1),
        UInt64(2),
        (
            UInt64(3),
            (
                String("a"),
                String("b"),
            ),
            UInt64(4),
        ),
        UInt64(5),
        UInt64(6),
    )
    (a, b, c) = nt[1:4]
    assert b[-1] == 4
    assert ((a, c),) == ((2, 5),)  # type: ignore[comparison-overlap]
    assert b[1][:] == ("a", "b")  # type: ignore[comparison-overlap]


@subroutine
def test_nested_singles(one: UInt64, *, reassign: bool) -> None:
    s = (
        (UInt64(0),),
        (one,),
        (UInt64(2),),
    )
    assert s[0][0] == 0
    assert s[0] == (0,)  # type: ignore[comparison-overlap]
    assert s[1][0] == 1
    assert s[1] == (one,)
    assert s[2][0] == 2
    assert s[2] == (2,)  # type: ignore[comparison-overlap]
    t = s[1]
    if reassign:
        s = (
            (UInt64(3),),
            (UInt64(4),),
            (UInt64(5),),
        )
    assert s[0][0] == (3 if reassign else 0)
    (tmp,) = s[2]
    assert tmp == (5 if reassign else 2)
    assert t == (one,)

    s0, (s1,), s2 = s
    s1 += one
    assert s1 == (5 if reassign else 2)
    assert s[1][0] == (4 if reassign else 1)


@subroutine
def test_nested_mutation() -> None:
    x = (
        (
            arc4.DynamicArray(
                arc4.UInt64(0),
            ),
        ),
    )
    x[0][0].append(arc4.UInt64(1))
    assert x[0][0].length == 2


@subroutine
def test_nested_iteration() -> None:
    x = UInt64(1)
    y = UInt64(2)
    total = UInt64(0)

    for t in ((x, y), (y, x), (x, x), (y, y)):
        a, b = t
        total += a + b

    for a, b in ((x, y), (y, x), (x, x), (y, y)):
        total += a + b

    assert total // 8 == 3
