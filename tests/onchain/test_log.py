from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_log(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "log")

    u64_bytes = [x.to_bytes(length=8) for x in range(8)]
    bytes_8 = b"\x08"
    assert response.logs == [
        u64_bytes[0],
        b"1",
        b"2",
        u64_bytes[3],
        b"",
        b"5" + u64_bytes[6] + u64_bytes[7] + bytes_8 + b"",
        b"_".join((b"5", u64_bytes[6], u64_bytes[7], bytes_8, b"")),
        b"_".join((b"5", u64_bytes[6], u64_bytes[7], bytes_8, b"")),
    ]
