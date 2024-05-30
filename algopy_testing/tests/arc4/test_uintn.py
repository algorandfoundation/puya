from algopy_testing import arc4
from algopy_testing.constants import MAX_UINT64
from algopy_testing.primitives.uint64 import UInt64


def test_unintn_init() -> None:
    assert arc4.UInt8(10).bytes == b"\n"
    assert arc4.UInt64(MAX_UINT64).native == UInt64(MAX_UINT64)
