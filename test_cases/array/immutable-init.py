from algopy import (
    FixedArray,
    ImmutableArray,
    ReferenceArray,
    UInt64,
    arc4,
)


class ImmutableArrayInitContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_immutable_array_init(self) -> None:
        a1 = ImmutableArray[UInt64]((UInt64(1), UInt64(2), UInt64(3)))

        a2 = ImmutableArray[UInt64](FixedArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a2.length
        assert a1[0] == a2[0]
        assert a1[1] == a2[1]
        assert a1[2] == a2[2]

        a3 = ImmutableArray[UInt64](ReferenceArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a3.length == 3
        assert a1[0] == a3[0]
        assert a1[1] == a3[1]
        assert a1[2] == a3[2]

        a4 = ImmutableArray[UInt64](ImmutableArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a4.length
        assert a1[0] == a4[0]
        assert a1[1] == a4[1]
        assert a1[2] == a4[2]

    @arc4.abimethod()
    def test_immutable_array_init_without_type_generic(self) -> None:
        a1 = ImmutableArray((UInt64(1), UInt64(2), UInt64(3)))

        a2 = ImmutableArray(FixedArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a2.length
        assert a1[0] == a2[0]
        assert a1[1] == a2[1]
        assert a1[2] == a2[2]

        a3 = ImmutableArray(ReferenceArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a3.length == 3
        assert a1[0] == a3[0]
        assert a1[1] == a3[1]
        assert a1[2] == a3[2]

        a4 = ImmutableArray(ImmutableArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a4.length
        assert a1[0] == a4[0]
        assert a1[1] == a4[1]
        assert a1[2] == a4[2]

    @arc4.abimethod()
    def test_reference_array_init(self) -> None:
        a1 = ReferenceArray[UInt64]((UInt64(1), UInt64(2), UInt64(3)))

        a2 = ReferenceArray[UInt64](FixedArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a2.length
        assert a1[0] == a2[0]
        assert a1[1] == a2[1]
        assert a1[2] == a2[2]

        a3 = ReferenceArray[UInt64](ImmutableArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a3.length == 3
        assert a1[0] == a3[0]
        assert a1[1] == a3[1]
        assert a1[2] == a3[2]

        a4 = ReferenceArray[UInt64](ReferenceArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a4.length
        assert a1[0] == a4[0]
        assert a1[1] == a4[1]
        assert a1[2] == a4[2]

    @arc4.abimethod()
    def test_reference_array_init_without_type_generic(self) -> None:
        a1 = ReferenceArray((UInt64(1), UInt64(2), UInt64(3)))

        a2 = ReferenceArray(FixedArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a2.length
        assert a1[0] == a2[0]
        assert a1[1] == a2[1]
        assert a1[2] == a2[2]

        a3 = ReferenceArray(ImmutableArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a3.length == 3
        assert a1[0] == a3[0]
        assert a1[1] == a3[1]
        assert a1[2] == a3[2]

        a4 = ReferenceArray(ReferenceArray((UInt64(1), UInt64(2), UInt64(3))))
        assert a1.length == a4.length
        assert a1[0] == a4[0]
        assert a1[1] == a4[1]
        assert a1[2] == a4[2]
