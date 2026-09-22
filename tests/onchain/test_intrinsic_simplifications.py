import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_intrinsic_simplifications(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "intrinsics" / "simplifications.py").client

    def call(method: str, args: list[object]) -> object:
        return client.send.call(au.AppClientMethodCallParams(method=method, args=args)).abi_return

    # select(0, 1, x) -> (x != 0)
    assert call("select_neq", [0]) == 0
    assert call("select_neq", [5]) == 1

    # extract_uint16(extract(src, 2, 0), 1) == extract_uint16(src, 3)
    src = bytes([0, 1, 2, 3, 4, 5, 6, 7])
    assert call("chained_extract", [src]) == int.from_bytes(src[3:5], "big")

    # (x + 5) + 3 == x + 8
    assert call("biguint_add_fold", [10]) == 18
    # (x * 5) * 3 == x * 15
    assert call("biguint_mul_fold", [10]) == 150
    # (x + y) + z
    assert call("biguint_add_no_fold", [10, 20, 30]) == 60
    # x + from_bytes(b"\x05") + 3 == x + 8
    assert call("biguint_add_bytes_const", [10]) == 18


def test_intrinsic_simplifications_oversized(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "intrinsics" / "simplifications.py").client

    # both methods leave a runtime b+ on an operand exceeding the 64-byte limit
    # (one via a byte-encoded sum, one via a 513-bit folded constant), which the
    # AVM rejects
    with pytest.raises(au.LogicError):
        client.send.call(au.AppClientMethodCallParams(method="biguint_add_oversized", args=[10]))
    with pytest.raises(au.LogicError):
        client.send.call(
            au.AppClientMethodCallParams(method="biguint_add_double_oversized", args=[10, 20])
        )
