import re

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_CONTRACT_PATH = TEST_CASES_DIR / "fixed_bytes_ops" / "abi_values.py"
_FEE = au.AlgoAmount.from_micro_algo(2000)


@pytest.fixture
def app_client(deployer: Deployer) -> au.AppClient:
    return deployer.create_bare((_CONTRACT_PATH, "FixedBytesABI")).client


@pytest.fixture
def check_client(deployer: Deployer) -> au.AppClient:
    return deployer.create_bare((_CONTRACT_PATH, "CheckABIApp")).client


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
