from algokit_common import public_key_from_address

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_address(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "constants" / "address_constant.py")
    sender_bytes = public_key_from_address(deployer_o.account.addr)
    assert response.logs == [sender_bytes]
