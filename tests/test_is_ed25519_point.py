import pytest

from puya.utils import is_ed25519_point

# (name, input, expected) copied verbatim from go-algorand's TestIsEdwards25519Point
_VECTORS = [
    (
        "basepoint",
        bytes.fromhex("5866666666666666666666666666666666666666666666666666666666666666"),
        True,
    ),
    (
        "identity small-order point",
        bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000000"),
        True,
    ),
    (
        "identity with non-canonical sign bit",
        bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000080"),
        True,
    ),
    (
        "non-canonical y equals p",
        bytes.fromhex("edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"),
        True,
    ),
    (
        "invalid y equals p plus 2",
        bytes.fromhex("efffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"),
        False,
    ),
    ("empty input", b"", False),
    ("short input", bytes(31), False),
    ("long input", bytes(33), False),
    # real LogicSig program-hash addresses from algorandfoundation/falcon-signatures'
    # lsig_address_kat.json (lsig_derivation.counter_cases): counter 0 hashes on-curve (rejected),
    # counter 1 off-curve (selected as the salted address)
    (
        "falcon lsig counter 0 (on-curve)",
        bytes.fromhex("3765d0000d9c8500bfe1285bb26e55eb5183ba25a5fb2574cddeca5a33f12e18"),
        True,
    ),
    (
        "falcon lsig counter 1 (off-curve)",
        bytes.fromhex("a72b0156bc6f3edf5293c4dc330bbbb9e6444cbbd549e67edb7ddfda6a30dff1"),
        False,
    ),
]


@pytest.mark.parametrize("case", _VECTORS, ids=[v[0] for v in _VECTORS])
def test_is_ed25519_point(case: tuple[str, bytes, bool]) -> None:
    _name, input_bytes, expected = case
    assert is_ed25519_point(input_bytes) is expected
