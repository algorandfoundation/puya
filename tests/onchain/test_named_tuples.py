import algokit_utils as au
from algokit_common import public_key_from_address

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_named_tuples(deployer: Deployer) -> None:
    result = deployer.create(TEST_CASES_DIR / "named_tuples" / "contract.py")
    client = result.client
    public_key = public_key_from_address(deployer.account.addr)

    response = client.send.call(
        au.AppClientMethodCallParams(
            method="build_tuple",
            args=[12, 343459043, "hello 123", public_key],
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_tuple",
            args=[response.abi_return],
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="test_tuple",
            args=[{"a": 34, "b": 53934433, "c": "hmmmm", "d": public_key}],
        )
    )

    expected_log = (1, 2, 3)
    expected_return = {"a": 2, "b": 3, "c": 1}
    response = client.send.call(au.AppClientMethodCallParams(method="build_tuple_side_effects"))
    assert response.abi_return == expected_return

    result_logs = response.confirmation.logs or []
    l1, l2, l3, _ = decode_logs(result_logs, len(result_logs) * "i")
    assert (l1, l2, l3) == expected_log
