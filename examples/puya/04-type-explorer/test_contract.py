from algopy import Bytes, UInt64, arc4
from algopy_testing import algopy_testing_context
from contract import TypeExplorer


class TestTypeExplorer:
    def test_uint64_add(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            result = contract.uint64_add(UInt64(10), UInt64(20))
            assert result == 30

    def test_uint64_pow(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            result = contract.uint64_pow(UInt64(2), UInt64(10))
            assert result == 1024

    def test_biguint_add(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            a = arc4.UInt512(100)
            b = arc4.UInt512(200)
            result = contract.biguint_add(a, b)
            assert result == arc4.UInt512(300)

    def test_biguint_mul(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            a = arc4.UInt512(7)
            b = arc4.UInt512(6)
            result = contract.biguint_mul(a, b)
            assert result == arc4.UInt512(42)

    def test_bytes_len(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            result = contract.bytes_len(Bytes(b"hello"))
            assert result == 5

    def test_itob_btoi_round_trip(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            original = UInt64(42)
            as_bytes = contract.itob_convert(original)
            back = contract.btoi_convert(as_bytes)
            assert back == 42

    def test_wide_add_no_carry(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            carry, low = contract.wide_add(UInt64(10), UInt64(20))
            assert carry == 0
            assert low == 30

    def test_wide_add_with_carry(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            max_u64 = UInt64(2**64 - 1)
            carry, low = contract.wide_add(max_u64, UInt64(2))
            assert carry == 1
            assert low == 1

    def test_wide_multiply(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            high, low = contract.wide_multiply(UInt64(5), UInt64(3))
            assert high == 0
            assert low == 15

    def test_wide_multiply_large(self) -> None:
        with algopy_testing_context():
            contract = TypeExplorer()
            contract.create()
            max_u64 = UInt64(2**64 - 1)
            high, low = contract.wide_multiply(max_u64, UInt64(2))
            assert high == 1
            assert low == 2**64 - 2
