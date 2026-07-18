import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_CONTROL_FLOW = EXAMPLES_DIR / "devportal" / "control_flow"


def test_if_else_is_rich(deployer: Deployer) -> None:
    client = deployer.create((_CONTROL_FLOW, "IfElseExample")).client

    def is_rich(balance: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method="is_rich", args=[balance])
        ).abi_return

    assert is_rich(5000) == "This account is rich!"
    assert is_rich(1001) == "This account is rich!"
    assert is_rich(1000) == "This account is doing well."
    assert is_rich(500) == "This account is doing well."
    assert is_rich(101) == "This account is doing well."
    assert is_rich(100) == "This account is poor :("
    assert is_rich(0) == "This account is poor :("


def test_ternary_is_even(deployer: Deployer) -> None:
    client = deployer.create((_CONTROL_FLOW, "IfElseExample")).client

    def is_even(number: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method="is_even", args=[number])
        ).abi_return

    assert is_even(0) == "Even"
    assert is_even(2) == "Even"
    assert is_even(10) == "Even"
    assert is_even(1) == "Odd"
    assert is_even(7) == "Odd"


def test_for_loop(deployer: Deployer) -> None:
    client = deployer.create((_CONTROL_FLOW, "ForLoopsExample")).client

    # urange(4) reversed -> [3, 2, 1, 0] assigned at forward index 0..3
    result = client.send.call(au.AppClientMethodCallParams(method="for_loop"))
    assert result.abi_return == [3, 2, 1, 0]


def test_match_get_day(deployer: Deployer) -> None:
    client = deployer.create((_CONTROL_FLOW, "MatchStatements")).client

    def get_day(date: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method="get_day", args=[date])
        ).abi_return

    expected = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    for day, name in enumerate(expected):
        assert get_day(day) == name

    # any value outside 0..6 falls through to the wildcard case
    assert get_day(7) == "Invalid day"
    assert get_day(100) == "Invalid day"


def test_while_loop(deployer: Deployer) -> None:
    client = deployer.create((_CONTROL_FLOW, "WhileLoopExample")).client

    # num=10: while num>5 (10->6) takes 5 iters, then num=6>5 once more -> num=5,
    # then num<=5 branch: num-=2 (5->3) iter 6, 3-=2 ->1 iter 7, num==1 breaks.
    result = client.send.call(au.AppClientMethodCallParams(method="loop"))
    assert result.abi_return == 7
