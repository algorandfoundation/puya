import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_logged_errs(deployer_o: Deployer) -> None:
    result = deployer_o.create_bare(TEST_CASES_DIR / "logged_errors")
    client = result.client

    def call(arg: int) -> au.SendAppTransactionResult[au.ABIValue]:
        return client.send.call(
            au.AppClientMethodCallParams(
                method="test_logged_errs",
                args=[arg],
            )
        )

    # arg=0 passes all assertions
    call(0)

    # arg=1 fails logged_assert with code only -> "ERR:01"
    with pytest.raises(au.LogicError, match="ERR:01"):
        call(1)

    # arg=2 fails logged_assert with code + message -> "ERR:02:arg is two"
    with pytest.raises(au.LogicError, match="ERR:02:arg is two"):
        call(2)

    # arg=3 fails logged_assert with custom prefix -> "AER:03"
    with pytest.raises(au.LogicError, match="AER:03"):
        call(3)

    # arg=4 fails unconditional logged_err -> "ERR:04"
    with pytest.raises(au.LogicError, match="ERR:04"):
        call(4)
