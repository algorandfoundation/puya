import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context
from contract import Counter


class TestCounter:
    def test_init_sets_counter_to_zero(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            assert contract.counter == 0

    def test_increment_returns_one(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            result = contract.increment()
            assert result == 1
            assert contract.counter == 1

    def test_multiple_increments_accumulate(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            contract.increment()
            contract.increment()
            result = contract.increment()
            assert result == 3
            assert contract.counter == 3

    def test_decrement_from_zero_raises(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            with pytest.raises(ArithmeticError):
                contract.decrement()

    def test_multiply_with_factor(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            contract.increment()
            contract.increment()
            contract.increment()
            result = contract.multiply(UInt64(3))
            assert result == 9
            assert contract.counter == 9

    def test_divide_with_divisor(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            for _ in range(8):
                contract.increment()
            result = contract.divide(UInt64(4))
            assert result == 2
            assert contract.counter == 2

    def test_divide_by_zero_raises(self) -> None:
        with algopy_testing_context():
            contract = Counter()

            contract.increment()
            with pytest.raises(ZeroDivisionError):
                contract.divide(UInt64(0))
