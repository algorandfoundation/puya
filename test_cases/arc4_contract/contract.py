from algopy import ARC4Contract, UInt64, public


class TestContract(ARC4Contract):
    @public
    def test_method(self, value: UInt64) -> UInt64:
        """Test method using @public decorator"""
        return value + UInt64(1)
