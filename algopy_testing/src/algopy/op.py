import hashlib
from enum import Enum

import algosdk
import coincurve
import nacl.exceptions
import nacl.signing
from algopy_testing.constants import MAX_BYTES_SIZE
from algopy_testing.contexts import state_context
from Cryptodome.Hash import keccak
from ecdsa import (  # type: ignore  # noqa: PGH003
    BadSignatureError,
    NIST256p,
    SECP256k1,
    VerifyingKey,
)

from algopy import Bytes, UInt64
from algopy.utils import as_bytes


class ECDSA(Enum):
    Secp256k1 = 0
    Secp256r1 = 1


def sha256(a: Bytes | bytes, /) -> Bytes:
    input_value = as_bytes(a, max_size=MAX_BYTES_SIZE)
    return Bytes(hashlib.sha256(input_value).digest())


def sha3_256(a: Bytes | bytes, /) -> Bytes:
    input_value = as_bytes(a, max_size=MAX_BYTES_SIZE)
    return Bytes(hashlib.sha3_256(input_value).digest())


def keccak256(a: Bytes | bytes, /) -> Bytes:
    input_value = as_bytes(a, max_size=MAX_BYTES_SIZE)
    hashed_value = keccak.new(data=input_value, digest_bits=256)
    return Bytes(hashed_value.digest())


def sha512_256(a: Bytes | bytes, /) -> Bytes:
    input_value = as_bytes(a, max_size=MAX_BYTES_SIZE)
    hash_object = hashlib.new("sha512_256", input_value)
    return Bytes(hash_object.digest())


def ed25519verify_bare(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    a, b, c = (as_bytes(x, max_size=MAX_BYTES_SIZE) for x in [a, b, c])

    try:
        verify_key = nacl.signing.VerifyKey(c)
        verify_key.verify(a, b)
    except nacl.exceptions.BadSignatureError:
        return False
    else:
        return True


def ed25519verify(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    NOTE: Differs from AVM behavior since it does not having access to the precompiled
    contract hash.
    Currently works by forwarding the call to ed25519verify_bare
    """
    with state_context() as state:
        program_hash = state.get_state("program_hash")

        if not program_hash:
            raise KeyError(
                "Run within 'algopy_testing.contexts.state_context' and set 'program_hash' value "
                "via 'state.update_state('program_hash', <value>)' "
            )

        decoded_address = algosdk.encoding.decode_address(algosdk.logic.address(program_hash))
        address_bytes = as_bytes(decoded_address, max_size=MAX_BYTES_SIZE)
        a = algosdk.constants.logic_data_prefix + address_bytes + a
        return ed25519verify_bare(a, b, c)


def ecdsa_verify(  # noqa: PLR0913
    v: ECDSA,
    a: Bytes | bytes,
    b: Bytes | bytes,
    c: Bytes | bytes,
    d: Bytes | bytes,
    e: Bytes | bytes,
    /,
) -> bool:
    data_bytes, sig_r_bytes, sig_s_bytes, pubkey_x_bytes, pubkey_y_bytes = (
        as_bytes(x, max_size=MAX_BYTES_SIZE) for x in [a, b, c, d, e]
    )

    curve_map = {
        ECDSA.Secp256k1: SECP256k1,
        ECDSA.Secp256r1: NIST256p,
    }

    curve = curve_map.get(v)
    if curve is None:
        raise ValueError(f"Unsupported ECDSA curve: {v}")

    try:
        public_key = b"\x04" + pubkey_x_bytes + pubkey_y_bytes
        vk = VerifyingKey.from_string(public_key, curve=curve)

        # Concatenate R and S components to form the signature
        signature = sig_r_bytes + sig_s_bytes
        vk.verify_digest(signature, data_bytes)
    except BadSignatureError:
        return False
    return True


def ecdsa_pk_recover(
    v: ECDSA, a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, d: Bytes | bytes, /
) -> tuple[Bytes, Bytes]:
    if v is not ECDSA.Secp256k1:
        raise ValueError(f"Unsupported ECDSA curve: {v}")

    data_bytes = as_bytes(a, max_size=MAX_BYTES_SIZE)
    r_bytes = as_bytes(c, max_size=MAX_BYTES_SIZE)
    s_bytes = as_bytes(d, max_size=MAX_BYTES_SIZE)
    recovery_id = int(b)

    if len(r_bytes) != 32 or len(s_bytes) != 32:
        raise ValueError("Invalid length for r or s bytes.")

    signature_rs = r_bytes + s_bytes + bytes([recovery_id])

    try:
        public_key = coincurve.PublicKey.from_signature_and_message(
            signature_rs, data_bytes, hasher=None
        )
        pubkey_x, pubkey_y = public_key.point()
    except Exception as e:
        raise ValueError(f"Failed to recover public key: {e}") from e
    else:
        return Bytes(pubkey_x.to_bytes(32, byteorder="big")), Bytes(
            pubkey_y.to_bytes(32, byteorder="big")
        )


def ecdsa_pk_decompress(v: ECDSA, a: Bytes | bytes, /) -> tuple[Bytes, Bytes]:
    if v not in [ECDSA.Secp256k1, ECDSA.Secp256r1]:
        raise ValueError(f"Unsupported ECDSA curve: {v}")

    compressed_pubkey = as_bytes(a, max_size=MAX_BYTES_SIZE)

    try:
        public_key = coincurve.PublicKey(compressed_pubkey)
        pubkey_x, pubkey_y = public_key.point()
    except Exception as e:
        raise ValueError(f"Failed to decompress public key: {e}") from e
    else:
        return Bytes(pubkey_x.to_bytes(32, byteorder="big")), Bytes(
            pubkey_y.to_bytes(32, byteorder="big")
        )
