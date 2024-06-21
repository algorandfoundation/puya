import math

import algopy
import pytest
from algopy_testing.constants import MAX_UINT64
from algopy_testing.models.unsigned_builtins import uenumerate, urange


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
def test_uenumerate_iter(args: list[int]) -> None:
    for x1, x2 in zip(uenumerate(urange(*args)), enumerate(range(*args)), strict=True):
        assert isinstance(x1[0], algopy.UInt64)
        assert x1[0] == x2[0]
        assert x1[1] == x2[1]


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
def test_uenumerate_reversed(args: list[int]) -> None:
    for x1, x2 in zip(
        reversed(uenumerate(urange(*args))), reversed(list(enumerate(range(*args)))), strict=True
    ):
        assert isinstance(x1[0], algopy.UInt64)
        assert x1[0] == x2[0]
        assert x1[1] == x2[1]
