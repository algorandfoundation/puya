import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context
from contract import compute_mint, compute_swap, wide_mul_div

LP_TOTAL = 10_000_000_000


class TestComputeSwap:
    def test_basic_swap(self) -> None:
        with algopy_testing_context():
            # 1000 in, 10000 reserve each side
            # numerator = 10000 * 1000 * 9970 = 99_700_000_000
            # denominator = 10000 * 10000 + 1000 * 9970 = 109_970_000
            # result = 906
            result = compute_swap(UInt64(1000), UInt64(10_000), UInt64(10_000))
            assert result == 906

    def test_large_reserves(self) -> None:
        with algopy_testing_context():
            result = compute_swap(UInt64(1_000_000), UInt64(1_000_000_000), UInt64(1_000_000_000))
            assert result == 996_006

    def test_small_swap(self) -> None:
        with algopy_testing_context():
            result = compute_swap(UInt64(1), UInt64(1_000_000), UInt64(1_000_000))
            # numerator = 1e6 * 1 * 9970 = 9_970_000_000
            # denominator = 1e6 * 10000 + 1 * 9970 = 10_000_009_970
            # result = 0 (integer division)
            assert result == 0

    def test_asymmetric_reserves(self) -> None:
        with algopy_testing_context():
            result = compute_swap(UInt64(500), UInt64(5_000), UInt64(20_000))
            # numerator = 20000 * 500 * 9970 = 99_700_000_000
            # denominator = 5000 * 10000 + 500 * 9970 = 54_985_000
            # result = 1813
            assert result == 1813


class TestWideMulDiv:
    def test_basic(self) -> None:
        with algopy_testing_context():
            result = wide_mul_div(UInt64(100), UInt64(200), UInt64(50))
            assert result == 400

    def test_large_values_no_overflow(self) -> None:
        with algopy_testing_context():
            # Would overflow UInt64 as intermediate: 2^32 * 2^32 = 2^64
            result = wide_mul_div(UInt64(2**32), UInt64(2**32), UInt64(2))
            assert result == 2**63

    def test_exact_division(self) -> None:
        with algopy_testing_context():
            result = wide_mul_div(UInt64(1_000_000), UInt64(1_000_000), UInt64(1_000_000))
            assert result == 1_000_000

    def test_truncation(self) -> None:
        with algopy_testing_context():
            # 7 * 3 / 2 = 10 (truncated from 10.5)
            result = wide_mul_div(UInt64(7), UInt64(3), UInt64(2))
            assert result == 10


class TestComputeMintInitial:
    def test_equal_amounts(self) -> None:
        with algopy_testing_context():
            # sqrt(10000 * 10000) = 10000
            result = compute_mint(
                pool_balance=UInt64(LP_TOTAL),
                a_balance=UInt64(10_000),
                b_balance=UInt64(10_000),
                a_amount=UInt64(10_000),
                b_amount=UInt64(10_000),
            )
            assert result == 10_000

    def test_different_amounts(self) -> None:
        with algopy_testing_context():
            # sqrt(100 * 400) = sqrt(40000) = 200
            result = compute_mint(
                pool_balance=UInt64(LP_TOTAL),
                a_balance=UInt64(100),
                b_balance=UInt64(400),
                a_amount=UInt64(100),
                b_amount=UInt64(400),
            )
            assert result == 200

    def test_large_amounts(self) -> None:
        with algopy_testing_context():
            # sqrt(1e6 * 1e6) = 1e6
            result = compute_mint(
                pool_balance=UInt64(LP_TOTAL),
                a_balance=UInt64(1_000_000),
                b_balance=UInt64(1_000_000),
                a_amount=UInt64(1_000_000),
                b_amount=UInt64(1_000_000),
            )
            assert result == 1_000_000


class TestComputeMintSubsequent:
    def test_proportional_mint(self) -> None:
        with algopy_testing_context():
            # Existing pool: issued = LP_TOTAL - 9_999_990_000 = 10_000
            # a_balance = 10_100 (10000 existing + 100 deposited)
            # a_ratio = (100 * 10000) / (10100 - 100) = 100
            # b_ratio = same = 100
            result = compute_mint(
                pool_balance=UInt64(LP_TOTAL - 10_000),
                a_balance=UInt64(10_100),
                b_balance=UInt64(10_100),
                a_amount=UInt64(100),
                b_amount=UInt64(100),
            )
            assert result == 100

    def test_uses_smaller_ratio(self) -> None:
        with algopy_testing_context():
            # issued = 10_000
            # a_ratio = (100 * 10000) / (10100 - 100) = 100
            # b_ratio = (200 * 10000) / (10200 - 200) = 200
            # min(100, 200) = 100
            result = compute_mint(
                pool_balance=UInt64(LP_TOTAL - 10_000),
                a_balance=UInt64(10_100),
                b_balance=UInt64(10_200),
                a_amount=UInt64(100),
                b_amount=UInt64(200),
            )
            assert result == 100


class TestIntegration:
    @pytest.mark.skip(
        reason="Full bootstrap/swap requires complex itxn + asset balance mocking not supported"
    )
    def test_bootstrap_and_swap(self) -> None:
        pass
