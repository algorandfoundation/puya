import random

import algokit_utils as au

from tests import AWST_DIR
from tests.utils.deployer import Deployer


def test_scc_vn_merged(deployer_o: Deployer) -> None:
    client = deployer_o.create(AWST_DIR / "scc_vn_merged").client

    def call(a: int, b: int, c: int, n: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method="run", args=[a, b, c, n], note=random.randbytes(8))
        ).abi_return

    # branchy_alternating(a, b, c, n) returns 2*(a|b) + n*(n-1)/2
    # (both branches initialise x and y to commutative-equivalent values, then
    # the loop swaps x and y each iteration. Either way x+y = 2*(a|b)).
    for a, b, c, n in [
        (0, 0, 0, 0),
        (10, 20, 0, 0),
        (10, 20, 1, 3),
        (10, 20, 0, 4),
        (7, 13, 1, 5),
        (7, 13, 0, 6),
    ]:
        expected = 2 * (a | b) + n * (n - 1) // 2
        actual = call(a, b, c, n)
        assert (
            actual == expected
        ), f"branchy_alternating({a}, {b}, {c}, {n}) gave {actual}, expected {expected}"
