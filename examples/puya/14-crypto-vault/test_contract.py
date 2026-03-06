import hashlib

from algopy import Bytes, UInt64
from algopy_testing import algopy_testing_context
from contract import CryptoVault
from nacl.signing import SigningKey


class TestCryptoVault:
    def test_hash_sha256(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            data = Bytes(b"hello")
            result = contract.hash_sha256(data)
            expected = hashlib.sha256(b"hello").digest()
            assert result == Bytes(expected)

    def test_hash_sha3_256(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            data = Bytes(b"hello")
            result = contract.hash_sha3_256(data)
            expected = hashlib.sha3_256(b"hello").digest()
            assert result == Bytes(expected)

    def test_hash_sha512_256(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            data = Bytes(b"hello")
            result = contract.hash_sha512_256(data)
            expected = hashlib.new("sha512_256", b"hello").digest()
            assert result == Bytes(expected)

    def test_hash_keccak256(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            data = Bytes(b"hello")
            result = contract.hash_keccak256(data)
            # Known keccak-256 digest of b"hello"
            expected = bytes.fromhex(
                "1c8aff950685c2ed4bc3174f3472287b56d9517b9c948127319a09a7a36deac8"
            )
            assert result == Bytes(expected)

    def test_verify_ed25519_valid(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            signing_key = SigningKey.generate()
            message = b"test message"
            signed = signing_key.sign(message)
            signature = signed.signature
            public_key = signing_key.verify_key.encode()
            result = contract.verify_ed25519(Bytes(message), Bytes(signature), Bytes(public_key))
            assert result is True

    def test_verify_ed25519_invalid(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            signing_key = SigningKey.generate()
            message = b"test message"
            signed = signing_key.sign(message)
            signature = signed.signature
            wrong_key = SigningKey.generate().verify_key.encode()
            result = contract.verify_ed25519(Bytes(message), Bytes(signature), Bytes(wrong_key))
            assert result is False

    def test_scratch_store_and_load(self) -> None:
        with algopy_testing_context():
            contract = CryptoVault()
            result = contract.scratch_store_and_load(UInt64(42), Bytes(b"hello"))
            assert result is True
