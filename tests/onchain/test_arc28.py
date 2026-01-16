import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_arc28(deployer: Deployer) -> None:
    result = deployer.create(EXAMPLES_DIR / "arc_28")
    client = result.client

    a = 42
    b = 12
    call_result = client.send.call(
        au.AppClientMethodCallParams(method="emit_swapped", args=[a, b])
    )
    logs = call_result.confirmation.logs
    events = decode_logs(logs, "bbb")
    for event in events:
        assert isinstance(event, bytes)
        event_sig = event[:4]
        event_data = event[4:]
        assert event_sig == bytes.fromhex("1ccbd925")
        assert event_data == b.to_bytes(length=8) + a.to_bytes(length=8)
