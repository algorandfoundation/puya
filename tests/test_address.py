from puya import algo_constants
from puya.utils import Address


def test_incorrectly_sized_address() -> None:
    garbage = Address.parse("bad")
    assert not garbage.is_valid
    assert garbage.public_key == b""
    assert garbage.check_sum == b""


def test_incorrectly_encoded_address() -> None:
    garbage = Address.parse("^" * algo_constants.ENCODED_ADDRESS_LENGTH)
    assert not garbage.is_valid
    assert garbage.public_key == b""
    assert garbage.check_sum == b""


def test_zero_address() -> None:
    address = Address.parse(algo_constants.ZERO_ADDRESS)
    assert address.is_valid
    assert address.public_key == b"\x00" * 32
    assert address.check_sum == bytes.fromhex("0c74e554")
