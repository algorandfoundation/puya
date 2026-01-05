import typing

from algopy import ARC4Contract, Struct, UInt64, arc4, public, subroutine


class ARC4TestStruct(arc4.Struct):
    value: arc4.UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value.as_uint64() * times


class TestStruct(Struct):
    value: UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value * times


class TestNamedTuple(typing.NamedTuple):
    value: UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value * times


class GroupedMethods(typing.NamedTuple):
    @subroutine(inline=False)
    def never_inlined_usually_inlined(self, v: UInt64) -> UInt64:
        return v + UInt64(1)

    @subroutine(inline=True)
    def always_inlined_not_usually_inlined(self, v: UInt64) -> None:
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))

    def usually_inlined(self, v: UInt64) -> UInt64:
        return v + UInt64(1)

    def not_usually_inlined(self, v: UInt64) -> None:
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))
        arc4.emit(ARC4TestStruct(arc4.UInt64(v)))


class TestContract(ARC4Contract):
    @public
    def test(self, expected: UInt64) -> None:
        assert expected == self.arc4_struct_test()
        assert expected == self.struct_test()
        assert expected == self.named_tuple_test()

        # Every method is called twice for a simple reason: if a method is only called once it
        # makes no sense to emit it separately (doing that adds callsub/proto/retsub machinery and
        # limits the ability of our optimizer).
        # Calling a method twice forces the optimizer to decide if the contract-size wins outweigh
        # the function-calling ceremony.
        assert UInt64(3) == GroupedMethods().never_inlined_usually_inlined(UInt64(2))
        assert UInt64(3) == GroupedMethods().never_inlined_usually_inlined(UInt64(2))
        assert UInt64(3) == GroupedMethods().usually_inlined(UInt64(2))
        assert UInt64(3) == GroupedMethods().usually_inlined(UInt64(2))
        GroupedMethods().always_inlined_not_usually_inlined(UInt64(2))
        GroupedMethods().always_inlined_not_usually_inlined(UInt64(2))
        GroupedMethods().not_usually_inlined(UInt64(2))
        GroupedMethods().not_usually_inlined(UInt64(2))

    def arc4_struct_test(self) -> UInt64:
        arc4_struct = ARC4TestStruct(arc4.UInt64(9))
        return arc4_struct.return_value_times(UInt64(2))

    def struct_test(self) -> UInt64:
        struct = TestStruct(UInt64(9))
        return struct.return_value_times(UInt64(2))

    def named_tuple_test(self) -> UInt64:
        named_tuple = TestNamedTuple(UInt64(9))
        return named_tuple.return_value_times(UInt64(2))
