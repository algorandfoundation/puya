import typing

from algopy import ARC4Contract, Struct, UInt64, arc4, public


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


class TestContract(ARC4Contract):
    @public
    def test(self, expected: UInt64) -> None:
        assert expected == self.arc4_struct_test()
        assert expected == self.struct_test()
        assert expected == self.named_tuple_test()

    def arc4_struct_test(self) -> UInt64:
        arc4_struct = ARC4TestStruct(arc4.UInt64(9))
        return arc4_struct.return_value_times(UInt64(2))

    def struct_test(self) -> UInt64:
        struct = TestStruct(UInt64(9))
        return struct.return_value_times(UInt64(2))

    def named_tuple_test(self) -> UInt64:
        named_tuple = TestNamedTuple(UInt64(9))
        return named_tuple.return_value_times(UInt64(2))
