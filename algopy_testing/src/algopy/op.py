import hashlib

import nacl.exceptions
import nacl.signing
from Cryptodome.Hash import keccak

from algopy import Bytes


def sha256(a: Bytes | bytes, /) -> Bytes:
    if not isinstance(a, bytes | Bytes):
        raise TypeError("Input must be bytes or Bytes")

    input_value = a.value if isinstance(a, Bytes) else a
    return Bytes(hashlib.sha256(input_value).digest())


def sha3_256(a: Bytes | bytes, /) -> Bytes:
    if not isinstance(a, bytes | Bytes):
        raise TypeError("Input must be bytes or Bytes")

    input_value = a.value if isinstance(a, Bytes) else a
    return Bytes(hashlib.sha3_256(input_value).digest())


def keccak256(a: Bytes | bytes, /) -> Bytes:
    if not isinstance(a, bytes | Bytes):
        raise TypeError("Input must be bytes or Bytes")

    input_value = a.value if isinstance(a, Bytes) else a
    hashed_value = keccak.new(data=input_value, digest_bits=256)
    return Bytes(hashed_value.digest())


def sha512_256(a: Bytes | bytes, /) -> Bytes:
    if not isinstance(a, bytes | Bytes):
        raise TypeError("Input must be bytes or Bytes")

    input_value = a.value if isinstance(a, Bytes) else a
    hash_object = hashlib.new("sha512_256", input_value)
    return Bytes(hash_object.digest())


def ed25519verify_bare(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    if not all(isinstance(x, (bytes | Bytes)) for x in [a, b, c]):
        raise TypeError("All inputs must be bytes or Bytes")

    data = a.value if isinstance(a, Bytes) else a
    signature = b.value if isinstance(b, Bytes) else b
    pubkey = c.value if isinstance(c, Bytes) else c

    try:
        verify_key = nacl.signing.VerifyKey(pubkey)
        verify_key.verify(data, signature)
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

    return ed25519verify_bare(a, b, c)
