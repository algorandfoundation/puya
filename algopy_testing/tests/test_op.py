import typing
from pathlib import Path

import algopy
import algosdk
import coincurve
import ecdsa  # type: ignore  # noqa: PGH003
import ecdsa.util  # type: ignore  # noqa: PGH003
import nacl.signing
import pytest
from algopy_testing import op
from algopy_testing.context import algopy_testing_context
from algopy_testing.primitives.bytes import Bytes
from algopy_testing.primitives.uint64 import UInt64
from algosdk.v2client.algod import AlgodClient
from Cryptodome.Hash import keccak
from ecdsa import SECP256k1, SigningKey, curves
from pytest_mock import MockerFixture

from tests.common import AVMInvoker, create_avm_invoker

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "CryptoOps" / "data" / "CryptoOpsContract.arc32.json"

MAX_ARG_LEN = 2048
MAX_BYTES_SIZE = 4096


def _generate_ecdsa_test_data(curve: curves.Curve) -> dict[str, typing.Any]:
    sk = SigningKey.generate(curve=curve)
    vk = sk.verifying_key
    data = b"test data for ecdsa"
    message_hash = keccak.new(data=data, digest_bits=256).digest()

    signature = sk.sign_digest(message_hash, sigencode=ecdsa.util.sigencode_string)
    r, s = ecdsa.util.sigdecode_string(signature, sk.curve.order)
    recovery_id = 0  # Recovery ID is typically 0 or 1

    return {
        "data": Bytes(message_hash),
        "r": Bytes(r.to_bytes(32, byteorder="big")),
        "s": Bytes(s.to_bytes(32, byteorder="big")),
        "recovery_id": UInt64(recovery_id),
        "pubkey_x": Bytes(vk.to_string()[:32]),
        "pubkey_y": Bytes(vk.to_string()[32:]),
    }


@pytest.fixture(scope="module")
def get_crypto_ops_avm_result(algod_client: AlgodClient) -> AVMInvoker:
    return create_avm_invoker(APP_SPEC, algod_client)


@pytest.mark.parametrize(
    ("input_value", "pad_size"),
    [
        (b"", 0),
        (b"0" * (MAX_ARG_LEN - 14), 0),
        (b"abc", 0),
        (Bytes(b"abc").value, MAX_BYTES_SIZE - 3),
        (b"abc", MAX_BYTES_SIZE - 3),
    ],
)
def test_sha256(get_crypto_ops_avm_result: AVMInvoker, input_value: bytes, pad_size: int) -> None:
    avm_result = get_crypto_ops_avm_result("verify_sha256", a=input_value, pad_size=pad_size)
    result = op.sha256((b"\x00" * pad_size) + input_value)
    assert avm_result == result.value
    assert len(result.value) == 32


@pytest.mark.parametrize(
    ("input_value", "pad_size"),
    [
        (b"", 0),
        (b"0" * (MAX_ARG_LEN - 14), 0),
        (b"abc", 0),
        (Bytes(b"abc").value, MAX_BYTES_SIZE - 3),
        (b"abc", MAX_BYTES_SIZE - 3),
    ],
)
def test_sha3_256(
    get_crypto_ops_avm_result: AVMInvoker, input_value: bytes, pad_size: int
) -> None:
    avm_result = get_crypto_ops_avm_result("verify_sha3_256", a=input_value, pad_size=pad_size)
    result = op.sha3_256((b"\x00" * pad_size) + input_value)
    assert avm_result == result.value
    assert len(result.value) == 32


@pytest.mark.parametrize(
    ("input_value", "pad_size"),
    [
        (b"", 0),
        (b"0" * (MAX_ARG_LEN - 14), 0),
        (b"abc", 0),
        (Bytes(b"abc").value, MAX_BYTES_SIZE - 3),
        (b"abc", MAX_BYTES_SIZE - 3),
    ],
)
def test_keccak_256(
    get_crypto_ops_avm_result: AVMInvoker, input_value: bytes, pad_size: int
) -> None:
    avm_result = get_crypto_ops_avm_result("verify_keccak_256", a=input_value, pad_size=pad_size)
    result = op.keccak256((b"\x00" * pad_size) + input_value)
    assert avm_result == result.value
    assert len(result.value) == 32


@pytest.mark.parametrize(
    ("input_value", "pad_size"),
    [
        (b"", 0),
        (b"0" * (MAX_ARG_LEN - 14), 0),
        (b"abc", 0),
        (Bytes(b"abc").value, MAX_BYTES_SIZE - 3),
        (b"abc", MAX_BYTES_SIZE - 3),
    ],
)
def test_sha512_256(
    get_crypto_ops_avm_result: AVMInvoker, input_value: bytes, pad_size: int
) -> None:
    avm_result = get_crypto_ops_avm_result("verify_sha512_256", a=input_value, pad_size=pad_size)
    result = op.sha512_256((b"\x00" * pad_size) + input_value)
    assert avm_result == result.value
    assert len(result.value) == 32


def test_ed25519verify_bare(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    signing_key = nacl.signing.SigningKey.generate()
    public_key = signing_key.verify_key.encode()
    message = b"Test message for ed25519 verification"
    signature = signing_key.sign(message).signature

    sp = algod_client.suggested_params()
    sp.fee = 2000
    avm_result = get_crypto_ops_avm_result(
        "verify_ed25519verify_bare", a=message, b=signature, c=public_key, suggested_params=sp
    )
    result = op.ed25519verify_bare(message, signature, public_key)

    assert avm_result == result, "The AVM result should match the expected result"


def test_ed25519verify(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    approval = get_crypto_ops_avm_result.client.approval
    assert approval
    with algopy_testing_context() as ctx:
        ctx.patch_txn_fields(approval_program=algopy.Bytes(approval.raw_binary))

        # Prepare message and signing parameters
        message = b"Test message for ed25519 verification"
        sp = algod_client.suggested_params()
        sp.fee = 2000

        # Generate key pair and sign the message
        private_key, public_key = algosdk.account.generate_account()
        public_key = algosdk.encoding.decode_address(public_key)
        signature = algosdk.logic.teal_sign_from_program(private_key, message, approval.raw_binary)

        # Verify the signature using AVM and local op
        avm_result = get_crypto_ops_avm_result(
            "verify_ed25519verify", a=message, b=signature, c=public_key, suggested_params=sp
        )
        result = op.ed25519verify(message, signature, public_key)

        assert avm_result == result, "The AVM result should match the expected result"


def test_ed25519verify_no_context() -> None:
    # Ensure the function raises an error outside the state context
    with pytest.raises(RuntimeError, match="function must be run within an active context"):
        op.ed25519verify(b"", b"", b"")


def test_ecdsa_verify_k1(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    message_hash = bytes.fromhex(
        "f809fd0aa0bb0f20b354c6b2f86ea751957a4e262a546bd716f34f69b9516ae1"
    )
    sig_r = bytes.fromhex("f7f913754e5c933f3825d3aef22e8bf75cfe35a18bede13e15a6e4adcfe816d2")
    sig_s = bytes.fromhex("0b5599159aa859d79677f33280848ae4c09c2061e8b5881af8507f8112966754")
    pubkey_x = bytes.fromhex("a710244d62747aa8db022ddd70617240adaf881b439e5f69993800e614214076")
    pubkey_y = bytes.fromhex("48d0d337704fe2c675909d2c93f7995e199156f302f63c74a8b96827b28d777b")

    sp = algod_client.suggested_params()
    sp.fee = 5000

    avm_result = get_crypto_ops_avm_result(
        "verify_ecdsa_verify_k1",
        a=message_hash,
        b=sig_r,
        c=sig_s,
        d=pubkey_x,
        e=pubkey_y,
        suggested_params=sp,
    )
    result = op.ecdsa_verify(op.ECDSA.Secp256k1, message_hash, sig_r, sig_s, pubkey_x, pubkey_y)
    assert avm_result == result, "The AVM result should match the expected result"


def test_ecdsa_verify_r1(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    message_hash = bytes.fromhex(
        "f809fd0aa0bb0f20b354c6b2f86ea751957a4e262a546bd716f34f69b9516ae1"
    )
    sig_r = bytes.fromhex("18d96c7cda4bc14d06277534681ded8a94828eb731d8b842e0da8105408c83cf")
    sig_s = bytes.fromhex("7d33c61acf39cbb7a1d51c7126f1718116179adebd31618c4604a1f03b5c274a")
    pubkey_x = bytes.fromhex("f8140e3b2b92f7cbdc8196bc6baa9ce86cf15c18e8ad0145d50824e6fa890264")
    pubkey_y = bytes.fromhex("bd437b75d6f1db67155a95a0da4b41f2b6b3dc5d42f7db56238449e404a6c0a3")

    sp = algod_client.suggested_params()
    sp.fee = 5000

    avm_result = get_crypto_ops_avm_result(
        "verify_ecdsa_verify_r1",
        a=message_hash,
        b=sig_r,
        c=sig_s,
        d=pubkey_x,
        e=pubkey_y,
        suggested_params=sp,
    )
    result = op.ecdsa_verify(op.ECDSA.Secp256r1, message_hash, sig_r, sig_s, pubkey_x, pubkey_y)
    assert avm_result == result, "The AVM result should match the expected result"


def test_verify_ecdsa_recover_k1(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    test_data = _generate_ecdsa_test_data(SECP256k1)

    a = test_data["data"].value
    b = test_data["recovery_id"].value
    c = test_data["r"].value
    d = test_data["s"].value

    expected_x, expected_y = op.ecdsa_pk_recover(op.ECDSA.Secp256k1, a, b, c, d)
    sp = algod_client.suggested_params()
    sp.fee = 3000
    result = get_crypto_ops_avm_result(
        "verify_ecdsa_recover_k1",
        a=a,
        b=b,
        c=c,
        d=d,
        suggested_params=sp,
    )
    assert isinstance(result, list)
    result_x, result_y = bytes(result[0]), bytes(result[1])

    assert result_x == expected_x, "X coordinate mismatch"
    assert result_y == expected_y, "Y coordinate mismatch"


def test_verify_ecdsa_decompress_k1(
    algod_client: AlgodClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    test_data = _generate_ecdsa_test_data(SECP256k1)

    a = test_data["data"].value
    b = test_data["recovery_id"].value
    c = test_data["r"].value
    d = test_data["s"].value
    signature_rs = c + d + bytes([b])
    pk = coincurve.PublicKey.from_signature_and_message(signature_rs, a, hasher=None)

    sp = algod_client.suggested_params()
    sp.fee = 3000
    result = get_crypto_ops_avm_result(
        "verify_ecdsa_decompress_k1",
        a=pk.format(compressed=True),
        suggested_params=sp,
    )
    assert isinstance(result, list)
    result_x, result_y = bytes(result[0]), bytes(result[1])

    assert result_x == pk.point()[0].to_bytes(32, byteorder="big"), "X coordinate mismatch"
    assert result_y == pk.point()[1].to_bytes(32, byteorder="big"), "Y coordinate mismatch"


def test_verify_vrf_verify(
    algod_client: AlgodClient, get_crypto_ops_avm_result: AVMInvoker, mocker: MockerFixture
) -> None:
    """
    'verify_vrf' is not implemented, the test aims to confirm that its possible to mock while
    comparing against the real vrf_verify execution.
    """

    a: bytes = bytes.fromhex("528b9e23d93d0e020a119d7ba213f6beb1c1f3495a217166ecd20f5a70e7c2d7")
    b: bytes = bytes.fromhex(
        "372a3afb42f55449c94aaa5f274f26543e77e8d8af4babee1a6fbc1c0391aa9e6e0b8d8d7f4ed045d5b517fea8ad3566025ae90d2f29f632e38384b4c4f5b9eb741c6e446b0f540c1b3761d814438b04"
    )
    c = bytes.fromhex("3a2740da7a0788ebb12a52154acbcca1813c128ca0b249e93f8eb6563fee418d")

    def run_real_vrf_verify() -> tuple[Bytes, bool]:
        sp = algod_client.suggested_params()
        sp.fee = 6000
        result = get_crypto_ops_avm_result("verify_vrf_verify", a=a, b=b, c=c, suggested_params=sp)
        return (Bytes(bytes(result[0])), bool(result[1]))  # type: ignore  # noqa: PGH003

    def run_mocked_vrf_verify() -> tuple[Bytes, bool]:
        return op.vrf_verify(op.VrfVerify.VrfAlgorand, a, b, c)

    avm_result = run_real_vrf_verify()
    mocker.patch("algopy_testing.op.vrf_verify", return_value=(avm_result[0], True))
    mocked_result = run_mocked_vrf_verify()

    assert avm_result == mocked_result
