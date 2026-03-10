import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context
from contract import ArrayPlayground


class TestArrayPlayground:
    @pytest.mark.xfail(reason="algorand-python-testing: Array() requires positional arg")
    def test_array(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            length, popped, total = contract.test_array()
            assert length == 5
            assert popped == 40
            assert total == 159

    def test_reference_array(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            length, total, copy_length = contract.test_reference_array()
            assert length == 5
            assert total == 15
            assert copy_length == 4

    def test_immutable_array(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            length, replaced, pop_length = contract.test_immutable_array()
            assert length == 4
            assert replaced == 99
            assert pop_length == 3

    @pytest.mark.xfail(reason="algorand-python-testing: FixedArray.replace _length=0 bug")
    def test_fixed_array(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            length, total, replaced_first = contract.test_fixed_array()
            assert length == 4
            assert total == 18
            assert replaced_first == 100

    def test_freeze(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            frozen_length, total = contract.test_freeze()
            assert frozen_length == 5
            assert total == 15

    def test_urange_sum(self) -> None:
        with algopy_testing_context():
            contract = ArrayPlayground()

            result = contract.test_urange_sum(UInt64(10))
            assert result == 55

            result = contract.test_urange_sum(UInt64(20))
            assert result == 210
