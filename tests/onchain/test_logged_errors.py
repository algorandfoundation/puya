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

    # arg=1 fails logged_assert -> "ERR:01"
    with pytest.raises(au.LogicError, match="ERR:01"):
        call(1)

    # arg=2 fails logged_assert -> "ERR:arg02:arg is two"
    with pytest.raises(au.LogicError, match="ERR:arg02:arg is two"):
        call(2)

    # arg=3 fails logged_assert -> "AER:arg03"
    with pytest.raises(au.LogicError, match="AER:arg03"):
        call(3)

    # arg=4 fails logged_assert -> "AER:arg04:arg is 4"
    with pytest.raises(au.LogicError, match="AER:arg04:arg is 4"):
        call(4)

    # arg=5 fails logged_err -> "ERR:arg05"
    with pytest.raises(au.LogicError, match="ERR:arg05"):
        call(5)

    # arg=6 fails logged_err -> "ERR:06:arg was 6"
    with pytest.raises(au.LogicError, match="ERR:06:arg was 6"):
        call(6)

    # arg=7 fails logged_err -> "AER:arg07"
    with pytest.raises(au.LogicError, match="AER:arg07"):
        call(7)

    # arg=8 fails logged_err -> "AER:arg08:arg is eight (08)"
    with pytest.raises(au.LogicError, match=r"AER:arg08:arg is eight \(08\)"):
        call(8)
