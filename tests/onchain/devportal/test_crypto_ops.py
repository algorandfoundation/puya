import hashlib
from random import randbytes

import algokit_utils as au
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nacl.signing import SigningKey

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_CRYPTO_OPS = EXAMPLES_DIR / "devportal" / "crypto_ops"

# crypto opcodes are budget-hungry; pad the group with op-up app calls. Each
# app call in the group pools 700 opcode units, so _OP_UPS + 1 (the method
# call) covers the most expensive opcode here (vrf_verify, ~5700).
_OP_UPS = 10
# enough fee on the method call to cover itself + each op-up create/delete pair
_FEE = au.AlgoAmount.from_micro_algo(1000 * (2 * _OP_UPS + 1))


def _call(deployer: Deployer, client: au.AppClient, method: str, args: list[object]) -> object:
    """Call an abimethod inside a group padded with op-up txns for extra budget."""
    group = deployer.localnet.new_group()
    for _idx in range(_OP_UPS):
        # unique note so repeated calls with the same args don't collide as
        # "transaction already in ledger" duplicates
        group.add_transaction(deployer.create_op_up(randbytes(8)))
    group.add_app_call_method_call(
        client.params.call(au.AppClientMethodCallParams(method=method, args=args, static_fee=_FEE))
    )
    return group.send().returns[-1].value


# curve group orders; AVM ecdsa_verify requires canonical low-S signatures
_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_SECP256R1_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _ecdsa_low_s(curve_order: int, r: int, s: int) -> tuple[int, int]:
    if s > curve_order // 2:
        s = curve_order - s
    return r, s


# -- hashes -----------------------------------------------------------------


@pytest.mark.parametrize("data", [b"", b"hello world", b"\x00\xff" * 32])
def test_hashes_match_python_reference(deployer: Deployer, data: bytes) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    result = _call(deployer, client, "hashes", [data])
    assert isinstance(result, list | tuple)
    assert len(result) == 4
    sha256, sha3_256, sha512_256, keccak256 = result

    assert bytes(sha256) == hashlib.sha256(data).digest()
    assert bytes(sha3_256) == hashlib.sha3_256(data).digest()
    assert bytes(sha512_256) == hashlib.new("sha512_256", data).digest()
    # keccak256 (legacy padding) differs from sha3_256 (NIST padding)
    assert bytes(keccak256) != bytes(sha3_256)


def test_keccak256_matches_reference(deployer: Deployer) -> None:
    # legacy Keccak-256 (pre-NIST padding), distinct from SHA3-256
    try:
        from Cryptodome.Hash import keccak as _keccak
    except ImportError:  # pragma: no cover
        pytest.skip("pycryptodomex not available for keccak reference")

    client = deployer.create(_CRYPTO_OPS).client
    data = b"keccak test vector"
    result = _call(deployer, client, "hashes", [data])
    assert isinstance(result, list | tuple)
    keccak256 = bytes(result[3])

    expected = _keccak.new(digest_bits=256, data=data).digest()
    assert keccak256 == expected


def test_hashes_are_deterministic(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    data = b"determinism check"
    first = _call(deployer, client, "hashes", [data])
    second = _call(deployer, client, "hashes", [data])
    assert isinstance(first, list | tuple)
    assert isinstance(second, list | tuple)
    assert [bytes(h) for h in first] == [bytes(h) for h in second]


# -- ed25519 ----------------------------------------------------------------


def test_ed25519_bare_verifies_valid_signature(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    key = SigningKey.generate()
    data = b"signed message"
    signature = key.sign(data).signature
    public_key = key.verify_key.encode()

    ed_result = _call(deployer, client, "ed25519", [data, signature, public_key])
    assert isinstance(ed_result, list | tuple)
    bound, bare = ed_result
    # ed25519verify_bare checks the raw data and must succeed
    assert bare is True
    # ed25519verify (bound) signs over "ProgData"||program_hash||data, which the
    # bare signature does not satisfy, so it is False
    assert bound is False


def test_ed25519_bound_verifies_program_bound_signature(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    # ed25519verify binds the signature to the executing program: the signed
    # message is "ProgData" || program_address || data, where the program
    # address is sha512_256("Program" || approval_program)
    app = deployer.localnet.client.algod.application_by_id(client.app_id)
    approval_program = app.params.approval_program
    assert isinstance(approval_program, bytes)
    program_hash = hashlib.new("sha512_256", b"Program" + approval_program).digest()

    key = SigningKey.generate()
    data = b"program bound message"
    signature = key.sign(b"ProgData" + program_hash + data).signature
    public_key = key.verify_key.encode()

    ed_result = _call(deployer, client, "ed25519", [data, signature, public_key])
    assert isinstance(ed_result, list | tuple)
    bound, bare = ed_result
    assert bound is True
    # the bare variant sees only `data`, not the domain-separated message
    assert bare is False


def test_ed25519_rejects_tampered_data(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    key = SigningKey.generate()
    signature = key.sign(b"original").signature
    public_key = key.verify_key.encode()

    ed_result = _call(deployer, client, "ed25519", [b"tampered", signature, public_key])
    assert isinstance(ed_result, list | tuple)
    bound, bare = ed_result
    assert bare is False
    assert bound is False


def test_ed25519_rejects_wrong_public_key(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    key = SigningKey.generate()
    data = b"signed message"
    signature = key.sign(data).signature
    wrong_public_key = SigningKey.generate().verify_key.encode()

    ed_result = _call(deployer, client, "ed25519", [data, signature, wrong_public_key])
    assert isinstance(ed_result, list | tuple)
    bound, bare = ed_result
    assert bare is False
    assert bound is False


# -- ecdsa ------------------------------------------------------------------


def _ec_keypair(
    curve: ec.EllipticCurve,
) -> tuple[ec.EllipticCurvePrivateKey, bytes, bytes]:
    priv = ec.generate_private_key(curve)
    nums = priv.public_key().public_numbers()
    return priv, nums.x.to_bytes(32, "big"), nums.y.to_bytes(32, "big")


def _ec_sign(
    priv: ec.EllipticCurvePrivateKey, digest: bytes, curve_order: int
) -> tuple[bytes, bytes]:
    der = priv.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    r, s = utils.decode_dss_signature(der)
    r, s = _ecdsa_low_s(curve_order, r, s)
    return r.to_bytes(32, "big"), s.to_bytes(32, "big")


def test_ecdsa_secp256k1_verifies_valid_signature(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    priv, pub_x, pub_y = _ec_keypair(ec.SECP256K1())
    digest = hashlib.sha256(b"ecdsa secp256k1 message").digest()
    sig_r, sig_s = _ec_sign(priv, digest, _SECP256K1_N)

    ecdsa_result = _call(deployer, client, "ecdsa", [digest, sig_r, sig_s, pub_x, pub_y])
    assert isinstance(ecdsa_result, list | tuple)
    k1, r1 = ecdsa_result
    # signature was produced on Secp256k1, so only the k1 result is True
    assert k1 is True
    assert r1 is False


def test_ecdsa_secp256r1_verifies_valid_signature(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    priv, pub_x, pub_y = _ec_keypair(ec.SECP256R1())
    digest = hashlib.sha256(b"ecdsa secp256r1 message").digest()
    sig_r, sig_s = _ec_sign(priv, digest, _SECP256R1_N)

    ecdsa_result = _call(deployer, client, "ecdsa", [digest, sig_r, sig_s, pub_x, pub_y])
    assert isinstance(ecdsa_result, list | tuple)
    k1, r1 = ecdsa_result
    # signature was produced on Secp256r1, so only the r1 result is True
    assert k1 is False
    assert r1 is True


def test_ecdsa_secp256k1_rejects_tampered_data(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    priv, pub_x, pub_y = _ec_keypair(ec.SECP256K1())
    digest = hashlib.sha256(b"original ecdsa message").digest()
    sig_r, sig_s = _ec_sign(priv, digest, _SECP256K1_N)
    wrong_digest = hashlib.sha256(b"different ecdsa message").digest()

    ecdsa_result = _call(deployer, client, "ecdsa", [wrong_digest, sig_r, sig_s, pub_x, pub_y])
    assert isinstance(ecdsa_result, list | tuple)
    k1, r1 = ecdsa_result
    assert k1 is False
    assert r1 is False


def test_ecdsa_decompress_expands_pubkey(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    priv, pub_x, pub_y = _ec_keypair(ec.SECP256K1())
    compressed = priv.public_key().public_bytes(Encoding.X962, PublicFormat.CompressedPoint)
    assert len(compressed) == 33

    decompress_result = _call(deployer, client, "ecdsa_decompress", [compressed])
    assert isinstance(decompress_result, list | tuple)
    x, y = decompress_result
    # decompressing the compressed key yields the original (X, Y) components
    assert bytes(x) == pub_x
    assert bytes(y) == pub_y


def test_ecdsa_recover_returns_signer_pubkey(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    priv, pub_x, pub_y = _ec_keypair(ec.SECP256K1())
    digest = hashlib.sha256(b"ecdsa recover message").digest()
    sig_r, sig_s = _ec_sign(priv, digest, _SECP256K1_N)

    # the recovery id is not knowable from (r, s) alone; one of the two
    # candidate ids must recover the signer's public key
    recovered = []
    for recovery_id in (0, 1):
        result = _call(deployer, client, "ecdsa_recover", [digest, recovery_id, sig_r, sig_s])
        assert isinstance(result, list | tuple)
        x, y = result
        recovered.append((bytes(x), bytes(y)))
    assert (pub_x, pub_y) in recovered


# -- vrf --------------------------------------------------------------------

# ECVRF-ED25519-SHA512-Elligator2 test vector from draft-irtf-cfrg-vrf-03
# (appendix A.4, example 10: alpha is the empty string)
_VRF_PUBLIC_KEY = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
_VRF_PROOF = bytes.fromhex(
    "b6b4699f87d56126c9117a7da55bd0085246f4c56dbc95d20172612e9d38e8d7"
    "ca65e573a126ed88d4e30a46f80a666854d675cf3ba81de0de043c3774f06156"
    "0f55edc256a787afe701677c0f602900"
)
_VRF_OUTPUT = bytes.fromhex(
    "5b49b554d05c0cd5a5325376b3387de59d924fd1e13ded44648ab33c21349a60"
    "3f25b84ec5ed887995b33da5e3bfcb87cd2f64521c4c62cf825cffabbe5d31cc"
)


def test_vrf_verifies_known_test_vector(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client

    vrf_result = _call(deployer, client, "vrf", [b"", _VRF_PROOF, _VRF_PUBLIC_KEY])
    assert isinstance(vrf_result, list | tuple)
    output, verified = vrf_result
    assert verified is True
    assert bytes(output) == _VRF_OUTPUT


def test_vrf_rejects_invalid_proof(deployer: Deployer) -> None:
    client = deployer.create(_CRYPTO_OPS).client
    # an all-zero proof / public key cannot verify against a random message
    message = b"vrf message"
    proof = b"\x00" * 80
    public_key = b"\x00" * 32

    vrf_result = _call(deployer, client, "vrf", [message, proof, public_key])
    assert isinstance(vrf_result, list | tuple)
    output, verified = vrf_result
    assert verified is False
    # output is only meaningful when verified is True
    assert len(bytes(output)) == 64
