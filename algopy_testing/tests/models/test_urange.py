import math

import algopy
import pytest
from algopy_testing.constants import MAX_UINT64
from algopy_testing.models.unsigned_builtins import urange


@pytest.mark.parametrize(
    "args",
    [
        [4],
        [1, 10],
        [1, 15, 2],
        [0, 10],
        [0, MAX_UINT64, math.floor(MAX_UINT64 / 10)],
    ],
)
def test_urange_iter(args: list[int]) -> None:
    for x1, x2 in zip(urange(*args), range(*args), strict=True):
        assert isinstance(x1, algopy.UInt64)
        assert x1 == x2


@pytest.mark.parametrize(
    "args",
    [
        [4],
        [1, 10],
        [1, 15, 2],
        [0, 10],
        [0, MAX_UINT64, math.floor(MAX_UINT64 / 10)],
    ],
)
def test_urange_reversed(args: list[int]) -> None:
    for x1, x2 in zip(reversed(urange(*args)), reversed(range(*args)), strict=True):
        assert isinstance(x1, algopy.UInt64)
        assert x1 == x2


@pytest.mark.parametrize(
    "args",
    [
        [MAX_UINT64 + 1],
        [0, MAX_UINT64 + 1],
        [0, MAX_UINT64, MAX_UINT64 + 1],
    ],
)
def test_arg_overflows(args: list[int]) -> None:
    with pytest.raises(ValueError, match=f"expected value <= {MAX_UINT64}"):
        urange(*args)


@pytest.mark.parametrize(
    "args",
    [
        [-MAX_UINT64],
        [0, -MAX_UINT64],
        [0, MAX_UINT64, -MAX_UINT64],
        [-10, 10, 2],
    ],
)
def test_arg_underflows(args: list[int]) -> None:
    with pytest.raises(ValueError, match="expected positive value"):
        urange(*args)


@pytest.mark.parametrize(
    "args",
    [
        [],
        [0, 1, 2, 3],
    ],
)
def test_invalid_arg_numbers(args: list[int]) -> None:
    with pytest.raises(
        TypeError, match=r"range expected at (most 3 arguments)|(least 1 argument)"
    ):
        urange(*args)
