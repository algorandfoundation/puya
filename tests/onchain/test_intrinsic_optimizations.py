import hashlib
from collections.abc import Sequence

import algokit_utils as au
import pytest
from Cryptodome.Hash import keccak

from puya.utils import sha512_256_hash
from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


@pytest.mark.parametrize(
    "value_to_hash",
    [
        b"123456",
        b"",
        b"HASHME",
        b"\x00" * 65,
    ],
)
def test_intrinsic_optimizations_implementation_correct(
    deployer: Deployer, value_to_hash: bytes
) -> None:
    client = deployer.create(TEST_CASES_DIR / "intrinsics" / "optimizations.py").client

    response = client.send.call(au.AppClientMethodCallParams(method="all", args=[value_to_hash]))
    assert isinstance(response.abi_return, Sequence)

    sha256, sha3_256, sha512_256, keccak256 = response.abi_return
    assert sha256 == hashlib.sha256(value_to_hash).digest()
    assert sha3_256 == hashlib.sha3_256(value_to_hash).digest()
    assert sha512_256 == sha512_256_hash(value_to_hash)
    assert keccak256 == keccak.new(data=value_to_hash, digest_bits=256).digest()


def test_intrinsic_optimizations(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "intrinsics" / "optimizations.py").client

    response = client.send.call(au.AppClientMethodCallParams(method="sha256"))
    assert response.abi_return == hashlib.sha256(b"Hello World").digest()

    response = client.send.call(au.AppClientMethodCallParams(method="sha3_256"))
    assert response.abi_return == hashlib.sha3_256(b"Hello World").digest()

    response = client.send.call(au.AppClientMethodCallParams(method="sha512_256"))
    assert response.abi_return == sha512_256_hash(b"Hello World")

    response = client.send.call(au.AppClientMethodCallParams(method="keccak256"))
    assert response.abi_return == keccak.new(data=b"Hello World", digest_bits=256).digest()
