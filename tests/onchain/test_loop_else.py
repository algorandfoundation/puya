import algokit_utils as au
import pytest
from algokit_common import ZERO_ADDRESS

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_CONTRACT_PATH = TEST_CASES_DIR / "loop_else" / "loop_else.py"


def test_loop_else(deployer_o: Deployer) -> None:
    # Deploy with args that should fail - missing secret argument
    with pytest.raises(au.LogicError, match="access denied, missing secret argument\t\t<-- Error"):
        deployer_o.create_bare(
            _CONTRACT_PATH,
            args=[0, 1],
        )

    # Deploy with args that should fail - missing secret account
    with pytest.raises(au.LogicError, match="access denied, missing secret account\t\t<-- Error"):
        deployer_o.create_bare(
            _CONTRACT_PATH,
            args=[2, b"while_secret", 3],
        )

    # Deploy with all secrets - should succeed
    result = deployer_o.create_bare(
        _CONTRACT_PATH,
        args=[4, b"while_secret", 5],
        account_references=[ZERO_ADDRESS, deployer_o.account.addr],
    )
    assert result.logs == [b"found secret argument at idx=1 and secret account at idx=1"]
