from puya.utils import StableSet


def test_stableset_sub() -> None:
    five = StableSet[int](*range(5))
    three = StableSet[int](*range(3))
    assert five - three == {3, 4}
    assert three - five == set()


def test_stableset_mixed_sub() -> None:
    five = StableSet[int](*range(5))
    three = set[int](range(3))
    assert five - three == {3, 4}
    assert three - five == set()


def test_stableset_or() -> None:
    five = StableSet[int](*range(5))
    three = StableSet[int](*range(3))
    assert five | three == {0, 1, 2, 3, 4}
    assert three | five == {0, 1, 2, 3, 4}


def test_stableset_mixed_or() -> None:
    five = StableSet[int](*range(5))
    three = set[int](range(3))
    assert five | three == {0, 1, 2, 3, 4}
    assert three | five == {0, 1, 2, 3, 4}
