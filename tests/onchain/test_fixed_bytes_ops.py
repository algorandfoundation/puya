import re

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils import get_local_state_delta_as_dict
from tests.utils.deployer import Deployer

_TEST_CASE = TEST_CASES_DIR / "fixed_bytes_ops"
_FEE = au.AlgoAmount.from_micro_algo(2000)


@pytest.fixture
def app_client(deployer: Deployer) -> au.AppClient:
    return deployer.create_bare((_TEST_CASE / "abi_values.py", "FixedBytesABI")).client


@pytest.fixture
def check_client(deployer: Deployer) -> au.AppClient:
    return deployer.create_bare((_TEST_CASE / "abi_values.py", "CheckABIApp")).client


def test_fixed_bytes_valid_calls(check_client: au.AppClient, app_client: au.AppClient) -> None:
    # Test valid calls - these should all succeed
    app_client.send.call(
        au.AppClientMethodCallParams(
            method="test_itxn_validate_caller_bytes",
            args=[check_client.app_id, b"hello world"],
            static_fee=_FEE,
        ),
    )

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="test_itxn_validate_callee_manual",
            args=[check_client.app_id, b"hello world"],
            static_fee=_FEE,
        ),
    )

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="test_itxn_validate_callee_router",
            args=[check_client.app_id, b"hello world"],
            static_fee=_FEE,
        ),
    )

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="test_static_to_dynamic_encoding",
            args=[check_client.app_id],
            static_fee=_FEE,
        ),
    )


def test_fixed_bytes_caller_validation_error(
    check_client: au.AppClient, app_client: au.AppClient
) -> None:
    # Test caller validation error - value too long
    with pytest.raises(au.LogicError, match="invalid size\t\t<-- Error"):
        app_client.send.call(
            au.AppClientMethodCallParams(
                method="test_itxn_validate_caller_bytes",
                args=[check_client.app_id, b"hello world!"],  # 12 bytes, expected 11
                static_fee=_FEE,
            ),
        )

    with pytest.raises(au.LogicError, match="inner tx 0 failed:") as manual_ex:
        app_client.send.call(
            au.AppClientMethodCallParams(
                method="test_itxn_validate_callee_manual",
                args=[check_client.app_id, b"hello world!"],  # 12 bytes, expected 11
                static_fee=_FEE,
            ),
        )

    assert (
        _get_inner_error(check_client.app_spec, manual_ex.value.message)
        == "callee method check failed"
    )

    with pytest.raises(au.LogicError, match="inner tx 0 failed:") as router_ex:
        app_client.send.call(
            au.AppClientMethodCallParams(
                method="test_itxn_validate_callee_router",
                args=[check_client.app_id, b"hello world!"],  # 12 bytes, expected 11
                static_fee=_FEE,
            ),
        )
    assert (
        _get_inner_error(check_client.app_spec, router_ex.value.message)
        == "invalid number of bytes for arc4.static_array<arc4.uint8, 11>"
    )


def _get_inner_error(app_spec: au.Arc56Contract, error_message: str) -> str | None:
    assert app_spec.source_info is not None, "require source info"
    match = re.search(r"pc=([0-9]+)", error_message)
    if not match:
        return None
    pc = int(match.group(1))
    try:
        (source_info,) = (si for si in app_spec.source_info.approval.source_info if pc in si.pc)
    except ValueError:
        return None
    return source_info.error_message


def test_fixed_bytes_ops(deployer_o: Deployer) -> None:
    result = deployer_o.create_with_op_up(
        _TEST_CASE / "contract.py",
        num_op_ups=3,
        on_complete=au.OnApplicationComplete.OptIn,
    )
    assert result.logs == [b"hello"]

    client = result.client
    sender = deployer_o.account.addr
    state_value = b"test"

    set_data_result = client.send.bare.call(
        au.AppClientBareCallParams(args=[b"set_state_data", state_value])
    )
    local_state_delta = get_local_state_delta_as_dict(
        set_data_result.confirmation.local_state_delta
    )
    assert local_state_delta == {sender: {b"local": state_value}}

    get_data_result = client.send.bare.call(
        au.AppClientBareCallParams(args=[b"get_state_data_or_assert"])
    )
    assert get_data_result.confirmation.logs == [state_value]

    augmented_result = client.send.bare.call(
        au.AppClientBareCallParams(
            args=[b"test_augmented_or_assignment_with_bytes", b"\x0f", b"\xff"]
        )
    )
    assert augmented_result.confirmation.logs == [b"\xff"]

    with pytest.raises(au.LogicError):
        client.send.bare.call(
            au.AppClientBareCallParams(
                args=[b"test_augmented_or_assignment_with_bytes", b"\x0f", b"\xff\xff"]
            )
        )

    client.send.bare.call(au.AppClientBareCallParams(args=[b"validate_fixed_bytes_3", b"abc"]))

    with pytest.raises(
        au.LogicError,
        match=r"invalid number of bytes for arc4\.static_array<arc4\.uint8, 3>\t\t<-- Error",
    ):
        client.send.bare.call(
            au.AppClientBareCallParams(args=[b"validate_fixed_bytes_3", b"1234"])
        )

    with pytest.raises(
        au.LogicError,
        match=r"invalid number of bytes for arc4\.static_array<arc4\.uint8, 3>\t\t<-- Error",
    ):
        client.send.bare.call(au.AppClientBareCallParams(args=[b"validate_fixed_bytes_3", b"12"]))
