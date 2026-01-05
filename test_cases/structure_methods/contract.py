import typing

from algopy import ARC4Contract, Struct, UInt64, arc4, public, subroutine


class ARC4TestStruct(arc4.Struct):
    value: arc4.UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value.as_uint64() * times

    @staticmethod
    def return1() -> UInt64:
        return UInt64(1)


class TestStruct(Struct):
    value: UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value * times

    @staticmethod
    def return1() -> UInt64:
        return UInt64(1)


class TestNamedTuple(typing.NamedTuple):
    value: UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value * times

    @staticmethod
    def return1() -> UInt64:
        return UInt64(1)


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
    def test(self) -> None:
        # Call instance methods from instance side
        assert UInt64(18) == ARC4TestStruct(arc4.UInt64(9)).return_value_times(UInt64(2))
        assert UInt64(18) == TestStruct(UInt64(9)).return_value_times(UInt64(2))
        assert UInt64(18) == TestNamedTuple(UInt64(9)).return_value_times(UInt64(2))

        # Call instance methods from class side
        assert UInt64(18) == ARC4TestStruct.return_value_times(
            ARC4TestStruct(arc4.UInt64(9)), UInt64(2)
        )
        assert UInt64(18) == TestStruct.return_value_times(TestStruct(UInt64(9)), UInt64(2))
        assert UInt64(18) == TestNamedTuple.return_value_times(
            TestNamedTuple(UInt64(9)), UInt64(2)
        )

        # Call static methods from class side
        assert UInt64(1) == ARC4TestStruct.return1()
        assert UInt64(1) == TestStruct.return1()
        assert UInt64(1) == TestNamedTuple.return1()

        # Call static methods from instance side
        assert UInt64(1) == ARC4TestStruct(arc4.UInt64(0)).return1()
        assert UInt64(1) == TestStruct(UInt64(0)).return1()
        assert UInt64(1) == TestNamedTuple(UInt64(0)).return1()

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
