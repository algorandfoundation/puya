import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_LOGGED_ERRORS = EXAMPLES_DIR / "devportal" / "logged_errors"


def test_deposit_and_withdraw(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    def call(method: str, amount: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method=method, args=[amount])
        ).abi_return

    # `balance` is global state, starting at 0 and updated by each call
    assert call("deposit", 100) == 100
    assert call("deposit", 50) == 150
    assert call("withdraw", 30) == 120
    assert call("withdraw", 120) == 0


def test_withdraw_zero_is_rejected(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    # logged_assert(amount > 0, ...) -> ERR:amountError01:amount must be positive
    with pytest.raises(au.LogicError, match="ERR:amountError01:amount must be positive"):
        client.send.call(au.AppClientMethodCallParams(method="withdraw", args=[0]))


def test_withdraw_insufficient_balance_is_rejected(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client
    client.send.call(au.AppClientMethodCallParams(method="deposit", args=[10]))

    # logged_assert(amount <= balance, ...) -> ERR:amountError02:insufficient balance
    with pytest.raises(au.LogicError, match="ERR:amountError02:insufficient balance"):
        client.send.call(au.AppClientMethodCallParams(method="withdraw", args=[50]))


def test_withdraw_desc_lands_in_arc56_source_info(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    # `desc=` does not change the on-chain logged output (covered above), but
    # becomes the plain-language errorMessage in the ARC-56 source info that
    # typed clients surface for the failing program counter
    source_info = client.app_spec.source_info
    assert source_info is not None
    messages = {e.error_message for e in source_info.approval.source_info if e.error_message}
    assert "Withdrawal amount must be greater than zero" in messages


def test_reject_returns_code_in_range(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    assert (
        client.send.call(au.AppClientMethodCallParams(method="reject", args=[42])).abi_return == 42
    )


def test_reject_out_of_range_codes_are_logged(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    # logged_err for the reserved zero code
    with pytest.raises(au.LogicError, match="ERR:codeRange00:code zero is reserved"):
        client.send.call(au.AppClientMethodCallParams(method="reject", args=[0]))

    # logged_err for codes above the permitted range
    with pytest.raises(au.LogicError, match="ERR:codeRange01:code out of range"):
        client.send.call(au.AppClientMethodCallParams(method="reject", args=[150]))


def test_reject_boundary_code(deployer: Deployer) -> None:
    client = deployer.create(_LOGGED_ERRORS).client

    # 100 is the highest accepted code; 101 is the first rejected one
    assert (
        client.send.call(au.AppClientMethodCallParams(method="reject", args=[100])).abi_return
        == 100
    )
    with pytest.raises(au.LogicError, match="ERR:codeRange01:code out of range"):
        client.send.call(au.AppClientMethodCallParams(method="reject", args=[101]))
