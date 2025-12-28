from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_inheritance_direct_method_invocation(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "inheritance" / "child.py")

    assert decode_logs(response.logs, "uu") == [
        "ChildContract.method called",
        "GrandParentContract.method called",
    ]
