import base64
import contextlib
import functools
import gzip
import math
import os
import typing
from collections.abc import Callable, Iterable, Iterator, MutableMapping, MutableSet, Sequence, Set
from contextvars import ContextVar
from pathlib import Path

import attrs

from puya.algo_constants import (
    ADDRESS_CHECKSUM_LENGTH,
    ENCODED_ADDRESS_LENGTH,
    MAX_APP_PAGE_SIZE,
    MAX_BYTES_LENGTH,
    MAX_UINT64,
    PUBLIC_KEY_HASH_LENGTH,
)


@attrs.frozen
class Address:
    address: str
    public_key: bytes
    check_sum: bytes
    is_valid: bool = attrs.field()

    @is_valid.default
    def _is_valid_factory(self) -> bool:
        if len(self.address) != ENCODED_ADDRESS_LENGTH:
            return False
        if len(self.public_key) != PUBLIC_KEY_HASH_LENGTH:
            return False
        if len(self.check_sum) != ADDRESS_CHECKSUM_LENGTH:
            return False
        check_sum = sha512_256_hash(self.public_key)[-ADDRESS_CHECKSUM_LENGTH:]
        return self.check_sum == check_sum

    @classmethod
    def from_public_key(cls, public_key: bytes) -> typing.Self:
        check_sum = sha512_256_hash(public_key)[-ADDRESS_CHECKSUM_LENGTH:]
        address_bytes = public_key + check_sum
        address = base64.b32encode(address_bytes).decode("utf8").rstrip("=")
        assert len(address) == ENCODED_ADDRESS_LENGTH
        return cls(
            address=address,
            public_key=public_key,
            check_sum=check_sum,
            is_valid=True,
        )

    @classmethod
    def parse(cls, address: str) -> typing.Self:
        # Pad address so it's a valid b32 string
        padded_address = address + (6 * "=")
        try:
            address_bytes = base64.b32decode(padded_address)
        except ValueError:
            # give empty values for any decode failure
            address_bytes = b""

        public_key_hash = address_bytes[:PUBLIC_KEY_HASH_LENGTH]
        check_sum = address_bytes[PUBLIC_KEY_HASH_LENGTH:]
        return cls(
            address=address,
            public_key=public_key_hash,
            check_sum=check_sum,
        )


def valid_base32(s: str) -> bool:
    """check if s is a valid base32 encoding string and fits into AVM bytes type"""
    try:
        value = base64.b32decode(s)
    except ValueError:
        return False
    return valid_bytes(value)
    # regex from PyTEAL, appears to be RFC-4648
    # ^(?:[A-Z2-7]{8})*(?:([A-Z2-7]{2}([=]{6})?)|([A-Z2-7]{4}([=]{4})?)|([A-Z2-7]{5}([=]{3})?)|([A-Z2-7]{7}([=]{1})?))?  # noqa: E501


def valid_base16(s: str) -> bool:
    try:
        value = base64.b16decode(s)
    except ValueError:
        return False
    return valid_bytes(value)


def valid_base64(s: str) -> bool:
    """check if s is a valid base64 encoding string and fits into AVM bytes type"""
    try:
        value = base64.b64decode(s, validate=True)
    except ValueError:
        return False
    return valid_bytes(value)
    # regex from PyTEAL, appears to be RFC-4648
    # ^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$


def valid_bytes(value: bytes) -> bool:
    return len(value) <= MAX_BYTES_LENGTH


def valid_int64(value: int) -> bool:
    return bool(0 <= value <= MAX_UINT64)


def valid_address(address: str) -> bool:
    """check if address is a valid address with checksum"""
    return Address.parse(address).is_valid


def sha512_256_hash(value: bytes) -> bytes:
    """
    Returns the SHA512/256 hash of a value. This is the hashing algorithm used
    to generate address checksums
    """
    from Cryptodome.Hash import SHA512

    sha = SHA512.new(truncate="256")
    sha.update(value)
    return sha.digest()


def method_selector_hash(method_signature: str) -> bytes:
    return sha512_256_hash(method_signature.encode("utf8"))[:4]


# TODO: what follows is an AI assisted translation of the check as performed in
# filippo.io/edwards25519 (Point.SetBytes).
# When a decision is made as to what the "single source of truth" for this check
# should be for python packages, we should replace this for said dependency.
def is_edwards25519_point(encoded: bytes) -> bool:
    """Whether ``encoded`` decodes as an Edwards25519 curve point, mirroring go-algorand's
    ``crypto.IsEdwards25519Point`` (filippo's ``Point.SetBytes`` succeeding); used to
    off-curve-harden LogicSig addresses by salting until the hash is *not* a point.

    Deliberately broader than strict Ed25519 public-key validation - small-order points and a
    non-canonical sign bit or ``y`` are accepted - so a strict library decoder can't be used.
    """
    # Edwards25519 curve parameters (RFC 8032)
    p: typing.Final = 2**255 - 19  # the field prime, 2^255 - 19
    d: typing.Final = (
        -121665 * pow(121666, -1, p)
    ) % p  # the curve constant d = -121665 / 121666 (mod p)

    if len(encoded) != 32:
        return False
    # y is the low 255 bits, little-endian; the top bit (the x sign) is masked off and, per the
    # reference decoder, plays no part in whether a point exists. Reducing mod p matches the
    # field arithmetic (so e.g. the non-canonical y == p behaves as y == 0).
    y = (int.from_bytes(encoded, "little") & ((1 << 255) - 1)) % p
    y2 = y * y % p
    u = (y2 - 1) % p
    v = (d * y2 + 1) % p
    # a point exists iff u/v is a square (mod p). Mirrors `field.Element.SqrtRatio`'s `wasSquare`
    # (constant-time, not a Legendre symbol) so edge cases like v == 0 match go-algorand: with
    # r = (u*v^3) * (u*v^7)^((p-5)/8), a root exists iff v*r^2 is u or -u.
    v3 = v * v % p * v % p
    v7 = v3 * v3 % p * v % p
    r = u * v3 % p * pow(u * v7 % p, (p - 5) // 8, p) % p
    check = v * r % p * r % p
    return check == u % p or check == (-u) % p


def attrs_extend[T: attrs.AttrsInstance](
    new_type: type[T], base_instance: attrs.AttrsInstance, **changes: object
) -> T:
    """Like attrs.evolve but allows creating a related type"""
    base_type = type(base_instance)
    old_type_fields = attrs.fields_dict(base_type)
    new_type_fields = attrs.fields(new_type)
    for a in new_type_fields:
        if not a.init:
            continue
        attr_name = a.name  # To deal with private attributes.
        init_name = a.alias
        if init_name not in changes and attr_name in old_type_fields:
            changes[init_name] = getattr(base_instance, attr_name)

    return new_type(**changes)


@functools.cache
def make_path_relative_to(*, to: Path, path: Path, walk_up: bool = False) -> str:
    with contextlib.suppress(ValueError):
        path = path.relative_to(to, walk_up=walk_up)
    return normalize_path(path)


_CWD = ContextVar[Path]("_CWD")
_CWD.set(Path.cwd())


@contextlib.contextmanager
def set_cwd(cwd: Path) -> Iterator[None]:
    token = _CWD.set(cwd)
    try:
        yield
    finally:
        _CWD.reset(token)


def get_cwd() -> Path:
    return _CWD.get()


def make_path_relative_to_cwd(path: Path) -> str:
    return make_path_relative_to(to=get_cwd(), path=path)


def unique[T](items: Iterable[T]) -> list[T]:
    return list(dict.fromkeys(items))


class StableSet[T](MutableSet[T]):
    __slots__ = ("_data",)

    def __init__(self, *items: T) -> None:
        self._data = dict.fromkeys(items)

    @classmethod
    def from_iter(cls, items: Iterable[T]) -> "StableSet[T]":
        result = StableSet.__new__(StableSet)
        result._data = dict.fromkeys(items)  # noqa: SLF001
        return result

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StableSet):
            return self._data.__eq__(other._data)
        else:
            return self._data.keys() == other

    def __ne__(self, other: object) -> bool:
        if isinstance(other, StableSet):
            return self._data.__ne__(other._data)
        else:
            return self._data.keys() != other

    def __contains__(self, x: object) -> bool:
        return self._data.__contains__(x)

    def __len__(self) -> int:
        return self._data.__len__()

    def __iter__(self) -> Iterator[T]:
        return self._data.__iter__()

    def add(self, value: T) -> None:
        self._data[value] = None

    def discard(self, value: T) -> None:
        self._data.pop(value, None)

    def intersection(self, other: Iterable[T]) -> "StableSet[T]":
        result = StableSet.__new__(StableSet)
        result._data = dict.fromkeys(k for k in self._data if k in other)  # noqa: SLF001
        return result

    def __or__(self, other: Iterable[T]) -> "StableSet[T]":  # type: ignore[override]
        result = StableSet.__new__(StableSet)
        if isinstance(other, StableSet):
            other_data = other._data
        else:
            other_data = dict.fromkeys(other)
        result._data = self._data | other_data
        return result

    def __ior__(self, other: Iterable[T]) -> typing.Self:  # type: ignore[override]
        if isinstance(other, StableSet):
            other_data = other._data
        else:
            other_data = dict.fromkeys(other)
        self._data |= other_data
        return self

    def __sub__(self, other: Set[T]) -> "StableSet[T]":
        result = StableSet.__new__(StableSet)
        if isinstance(other, StableSet):
            data: Iterable[T] = self._data.keys() - other._data.keys()
        else:
            data = (k for k in self._data if k not in other)
        result._data = dict.fromkeys(data)
        return result

    # have to override r variants as default impl does not work with our __init__
    __ror__ = __or__

    def __rsub__(self, other: Set[T]) -> "StableSet[T]":
        result = StableSet.__new__(StableSet)
        if isinstance(other, StableSet):
            data: Iterable[T] = other._data.keys() - self._data.keys()
        else:
            data = (k for k in other if k not in self._data)
        result._data = dict.fromkeys(data)
        return result

    def __repr__(self) -> str:
        return type(self).__name__ + "(" + ", ".join(map(repr, self._data)) + ")"


def lazy_setdefault[T, U](m: MutableMapping[T, U], /, key: T, default: Callable[[T], U]) -> U:
    """dict.setdefault, but with a callable"""
    try:
        return m[key]
    except KeyError:
        pass
    value = default(key)
    m[key] = value
    return value


_INVERT_ORDERED_BINARY_OP = str.maketrans("<>", "><")


def invert_ordered_binary_op(op: str) -> str:
    return op.translate(_INVERT_ORDERED_BINARY_OP)


def clamp(value: int, *, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value


def bits_to_bytes(bit_size: int) -> int:
    return int(math.ceil(bit_size / 8))


def round_bits_to_nearest_bytes(bit_size: int) -> int:
    return bits_to_bytes(bit_size) * 8


@contextlib.contextmanager
def pushd(new_dir: Path) -> Iterator[None]:
    with set_cwd(new_dir):
        yield


def normalise_path_to_str(path: Path) -> str:
    return str(path).replace("\\", "/")


def biguint_bytes_length(value: int) -> int:
    return math.ceil(value.bit_length() / 8.0)


def biguint_bytes_eval(value: int) -> bytes:
    byte_length = biguint_bytes_length(value)
    big_uint_bytes = value.to_bytes(byteorder="big", length=byte_length)
    return big_uint_bytes


def calculate_extra_program_pages(approval_program_length: int, clear_program_length: int) -> int:
    total_bytes = approval_program_length + clear_program_length
    return (total_bytes - 1) // MAX_APP_PAGE_SIZE


@typing.overload
def coalesce[T](arg1: T | None, arg2: T, /) -> T: ...


@typing.overload
def coalesce[T](arg1: T | None, arg2: T | None, arg3: T, /) -> T: ...


@typing.overload
def coalesce[T](*args: T | None) -> T | None: ...


def coalesce[T](*args: T | None) -> T | None:
    """Shorthand for `a if a is not None else b`, with eager evaluation as a tradeoff"""
    # REFACTOR: if there's a better way to do the above overloads, we should.
    #           the problem is you can't have a positional argument after *args,
    #           and we want to take the last one's type separately
    for arg in args:
        if arg is not None:
            return arg
    return None


def positive_index[T](idx: int, seq: Sequence[T]) -> int:
    return idx if idx >= 0 else len(seq) + idx


def set_add[T](set_: MutableSet[T], value: T) -> bool:
    """ensure item exists in a set, returning if it was added or not"""
    added = value not in set_
    set_.add(value)
    return added


def set_remove[T](set_: MutableSet[T], value: T) -> bool:
    removed = value in set_
    set_.discard(value)
    return removed


def normalize_path(path: Path) -> str:
    return str(path).replace(os.sep, "/")


def not_none[T](x: T | None) -> T:
    assert x is not None
    return x


def chunk_array[T](arr: list[T], size: int) -> list[list[T]]:
    return [arr[i : i + size] for i in range(0, len(arr), size)]


def read_text_from_maybe_compressed_file(path: Path) -> str:
    if path.suffix in (".gz", ".gzip"):
        with gzip.open(path, mode="rt", encoding="utf8") as fp:
            return fp.read()
    else:
        return path.read_text("utf8")
