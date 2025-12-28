import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils import get_local_state_delta_as_dict, get_state_delta_as_dict
from tests.utils.deployer import Deployer


def test_augmented_assignment(deployer_o: Deployer) -> None:
    result = deployer_o.create_with_op_up(
        TEST_CASES_DIR / "augmented_assignment" / "contract.py",
        num_op_ups=0,
        on_complete=au.OnApplicationComplete.OptIn,
        args=[0],
    )
    client = result.client
    sender = deployer_o.account.addr

    # Check initial state deltas from deploy
    global_delta = get_state_delta_as_dict(result.confirmation.global_state_delta)
    local_delta = get_local_state_delta_as_dict(result.confirmation.local_state_delta)

    # Initial values are not defined
    assert global_delta == {
        b"counter": None,
        b"global_uint": None,
        b"global_bytes": None,
    }
    assert local_delta == {
        sender: {
            b"my_uint": None,
            b"my_bytes": None,
        }
    }

    # First call with 1 arg
    call_result_1 = client.send.bare.call(
        au.AppClientBareCallParams(args=[(0).to_bytes(8, "big")])
    )
    increment_uint = 1
    expected_uint = increment_uint
    expected_bytes = increment_uint.to_bytes(byteorder="big", length=8)

    global_delta = get_state_delta_as_dict(call_result_1.confirmation.global_state_delta)
    local_delta = get_local_state_delta_as_dict(call_result_1.confirmation.local_state_delta)

    assert global_delta == {
        b"counter": 2,
        b"global_uint": expected_uint,
        b"global_bytes": expected_bytes,
    }
    assert local_delta == {
        sender: {
            b"my_uint": expected_uint,
            b"my_bytes": expected_bytes,
        }
    }

    # Second call with 2 args
    call_result_2 = client.send.bare.call(
        au.AppClientBareCallParams(args=[(0).to_bytes(8, "big"), (1).to_bytes(8, "big")])
    )
    increment_uint = 2
    expected_uint += increment_uint
    expected_bytes += increment_uint.to_bytes(byteorder="big", length=8)

    global_delta = get_state_delta_as_dict(call_result_2.confirmation.global_state_delta)
    local_delta = get_local_state_delta_as_dict(call_result_2.confirmation.local_state_delta)

    assert global_delta == {
        b"counter": 2,
        b"global_uint": expected_uint,
        b"global_bytes": expected_bytes,
    }
    assert local_delta == {
        sender: {
            b"my_uint": expected_uint,
            b"my_bytes": expected_bytes,
        }
    }
