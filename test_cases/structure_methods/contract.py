from algopy import ARC4Contract, UInt64, arc4, public


class TestStruct(arc4.Struct):
    value: arc4.UInt64

    def return_value_times(self, times: UInt64) -> UInt64:
        return self.value.as_uint64() * times


class TestContract(ARC4Contract):
    @public
    def test_method(self, value: UInt64) -> UInt64:
        """Test method using @public decorator"""
        return value + self.internal_method()

    def internal_method(self) -> UInt64:
        return TestStruct(arc4.UInt64(9)).return_value_times(UInt64(2))
