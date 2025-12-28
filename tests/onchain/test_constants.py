from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_byte_constants(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "constants" / "byte_constants.py")

    the_str, the_length = decode_logs(response.logs, "bi")
    expected = b"Base 16 encoded|Base 64 encoded|Base 32 encoded|UTF-8 Encoded"
    assert the_str == expected
    assert the_length == len(expected)
