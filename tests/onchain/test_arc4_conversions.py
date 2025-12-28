import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_FEE = au.AlgoAmount.from_micro_algo(10_000)


def test_arc4_conversions(deployer: Deployer) -> None:
    result = deployer.create(
        (TEST_CASES_DIR / "arc4_conversions", "TestContract"),
    )
    client = result.client

    # Call each test method - these have inner transactions
    client.send.call(
        au.AppClientMethodCallParams(method="test_literal_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_native_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_arc4_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_array_uint64_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_array_static_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_array_dynamic_encoding", static_fee=_FEE),
    )
    client.send.call(
        au.AppClientMethodCallParams(method="test_bytes_to_fixed", args=[False], static_fee=_FEE),
    )

    # Test error case
    with pytest.raises(au.LogicError, match="invalid size\t\t<-- Error"):
        client.send.call(
            au.AppClientMethodCallParams(
                method="test_bytes_to_fixed", args=[True], static_fee=_FEE
            ),
        )
