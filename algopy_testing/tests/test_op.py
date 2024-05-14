import typing
from pathlib import Path

import algokit_utils
import nacl.signing
import pytest
from algokit_utils import ApplicationClient, get_localnet_default_account
from algokit_utils.config import config
from algopy import Bytes, op
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from tests.common import AVMInvoker

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "CryptoOps" / "data" / "CryptoOpsContract.arc32.json"

MAX_ARG_LEN = 2048
MAX_BYTES_SIZE = 4096


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
    create_avm_invoker: typing.Callable[[ApplicationClient], AVMInvoker],
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
