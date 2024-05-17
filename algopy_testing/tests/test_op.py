import typing
from pathlib import Path

import algokit_utils
import algosdk
import coincurve
import ecdsa  # type: ignore  # noqa: PGH003
import ecdsa.util  # type: ignore  # noqa: PGH003
import nacl.signing
import pytest
from algokit_utils import ApplicationClient, get_localnet_default_account
from algokit_utils.config import config
from algopy import Bytes, UInt64, op
from algopy_testing.context import new_context
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from Cryptodome.Hash import keccak
from ecdsa import SECP256k1, SigningKey, curves

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


@pytest.fixture(scope="session")
def crypto_ops_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> ApplicationClient:
    config.configure(
        debug=True,
    )

    client = ApplicationClient(
        algod_client,
        APP_SPEC,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )

    return client


@pytest.fixture(scope="module")
def get_crypto_ops_avm_result(
    crypto_ops_client: ApplicationClient,
) -> AVMInvoker:
    return create_avm_invoker(crypto_ops_client)


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
    crypto_ops_client: ApplicationClient,
    get_crypto_ops_avm_result: AVMInvoker,
) -> None:
    assert crypto_ops_client.approval
    with new_context() as ctx:
        ctx.program_hash = crypto_ops_client.approval.raw_binary
        # Prepare message and signing parameters
        message = b"Test message for ed25519 verification"
        sp = algod_client.suggested_params()
        sp.fee = 2000

        # Generate key pair and sign the message
        private_key, public_key = algosdk.account.generate_account()
        public_key = algosdk.encoding.decode_address(public_key)
        signature = algosdk.logic.teal_sign_from_program(
            private_key, message, crypto_ops_client.approval.raw_binary
        )

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
    message_hash = (
        b"\xf8\t\xfd\n\xa0\xbb\x0f \xb3T\xc6\xb2\xf8n\xa7Q\x95zN&*Tk\xd7\x16\xf3Oi\xb9Qj\xe1"
    )
    sig_r = (
        b"\xf7\xf9\x13uN\\\x93?8%\xd3\xae\xf2.\x8b\xf7\\\xfe5\xa1\x8b\xed\xe1>\x15\xa6\xe4\xad"
        b"\xcf\xe8\x16\xd2"
    )
    sig_s = (
        b"\x0bU\x99\x15\x9a\xa8Y\xd7\x96w\xf32\x80\x84\x8a\xe4\xc0\x9c a\xe8\xb5\x88\x1a\xf8"
        b"P\x7f\x81\x12\x96gT"
    )
    pubkey_x = b"\xa7\x10$Mbtz\xa8\xdb\x02-\xddpar@\xad\xaf\x88\x1bC\x9e_i\x998\x00\xe6\x14!@v"
    pubkey_y = (
        b"H\xd0\xd37pO\xe2\xc6u\x90\x9d,\x93\xf7\x99^\x19\x91V\xf3\x02\xf6<t\xa8\xb9h'\xb2\x8dw{"
    )

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
    message_hash = (
        b"\xf8\t\xfd\n\xa0\xbb\x0f \xb3T\xc6\xb2\xf8n\xa7Q\x95zN&*Tk\xd7\x16\xf3Oi\xb9Qj\xe1"
    )
    sig_r = (
        b"\x18\xd9l|\xdaK\xc1M\x06'u4h\x1d\xed\x8a\x94\x82\x8e\xb71\xd8\xb8B\xe0\xda\x81\x05@"
        b"\x8c\x83\xcf"
    )
    sig_s = (
        b"}3\xc6\x1a\xcf9\xcb\xb7\xa1\xd5\x1cq&\xf1q\x81\x16\x17\x9a\xde\xbd1a\x8cF\x04\xa1\xf0"
        b";\\'J"
    )
    pubkey_x = (
        b"\xf8\x14\x0e;+\x92\xf7\xcb\xdc\x81\x96\xbck\xaa\x9c\xe8l\xf1\\\x18\xe8\xad\x01E\xd5"
        b"\x08$\xe6\xfa\x89\x02d"
    )
    pubkey_y = (
        b"\xbdC{u\xd6\xf1\xdbg\x15Z\x95\xa0\xdaKA\xf2\xb6\xb3\xdc]B\xf7\xdbV#\x84I\xe4"
        b"\x04\xa6\xc0\xa3"
    )

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
