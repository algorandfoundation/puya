import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils import get_local_state_delta_as_dict, get_state_delta_as_dict
from tests.utils.deployer import Deployer, encode_bare_args


def test_simplish(deployer_o: Deployer) -> None:
    result = deployer_o.create_bare(TEST_CASES_DIR / "simplish")
    client = result.client
    sender = deployer_o.account.addr
    nickname = b"My Nicky Nick"

    # OptIn call with nickname
    opt_in_result = client.send.bare.call(
        au.AppClientBareCallParams(
            args=[nickname],
        ),
        on_complete=au.OnApplicationComplete.OptIn,
    )
    assert not opt_in_result.confirmation.logs

    # Check local state delta
    local_state_delta = get_local_state_delta_as_dict(opt_in_result.confirmation.local_state_delta)

    assert local_state_delta == {sender: {b"name": nickname}}
    assert not opt_in_result.confirmation.global_state_delta

    # Call circle_report
    circle_report_result = client.send.bare.call(
        au.AppClientBareCallParams(args=encode_bare_args([b"circle_report", 123]))
    )
    assert circle_report_result.confirmation.logs == [
        b"Approximate area and circumference of circle with radius 123 = 47529, 772",
        b"Incrementing counter!",
    ]
    assert not circle_report_result.confirmation.local_state_delta

    # Check global state delta
    global_state_delta = get_state_delta_as_dict(
        circle_report_result.confirmation.global_state_delta
    )
    assert global_state_delta == {b"counter": 1}

    # Delete application
    delete_result = client.send.bare.call(on_complete=au.OnApplicationComplete.DeleteApplication)
    assert delete_result.confirmation.logs == [b"I was used 1 time(s) before I died"]
    assert not delete_result.confirmation.global_state_delta
    assert not delete_result.confirmation.local_state_delta
