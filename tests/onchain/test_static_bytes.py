import algokit_utils as au

from tests import AWST_DIR
from tests.utils.deployer import Deployer


def test_static_bytes(deployer: Deployer) -> None:
    client = deployer.create(AWST_DIR / "static_bytes").client

    res_receive_b32 = client.send.call(
        au.AppClientMethodCallParams(
            method="receiveB32",
            args=[bytes(32)],
        )
    )
    assert isinstance(res_receive_b32.abi_return, bytes)
    assert len(res_receive_b32.abi_return) == 32

    client.send.call(au.AppClientMethodCallParams(method="test"))
    client.send.call(au.AppClientMethodCallParams(method="testArray"))
