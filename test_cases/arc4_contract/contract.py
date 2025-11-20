from algopy import ARC4Contract, UInt64, public


class TestContract(ARC4Contract):
    @public
    def test_method(self, value: UInt64) -> UInt64:
        """Test method using @public decorator"""
        return value + self.internal_method()

    def internal_method(self) -> UInt64:
        return UInt64(1)
