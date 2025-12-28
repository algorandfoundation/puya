from nacl.signing import SigningKey

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_verify(deployer_o: Deployer) -> None:
    key = SigningKey.generate()
    data = b"random bytes"
    sig = key.sign(data).signature
    public_key = key.verify_key.encode()

    response = deployer_o.create_with_op_up(
        TEST_CASES_DIR / "edverify",
        num_op_ups=4,
        args=[data, sig, public_key],
    )
    (verify_outcome,) = decode_logs(response.logs, "i")

    assert verify_outcome == 1
