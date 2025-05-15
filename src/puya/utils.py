import base64
import contextlib
import functools
import math
import os
import typing
from collections.abc import Callable, Iterable, Iterator, MutableMapping, MutableSet, Sequence, Set
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
    public_key: bytes = b""
    check_sum: bytes = b""
    is_valid: bool = False

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
        if not (len(address) == ENCODED_ADDRESS_LENGTH and valid_base32(padded_address)):
            return cls(address)
        address_bytes = base64.b32decode(padded_address)
        if len(address_bytes) != PUBLIC_KEY_HASH_LENGTH + ADDRESS_CHECKSUM_LENGTH:
            return cls(address)

        public_key_hash = address_bytes[:PUBLIC_KEY_HASH_LENGTH]
        check_sum = address_bytes[PUBLIC_KEY_HASH_LENGTH:]
        verified_address = cls.from_public_key(public_key_hash)
        return cls(
            address=address,
            public_key=public_key_hash,
            check_sum=check_sum,
            is_valid=verified_address.check_sum == check_sum,
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


def make_path_relative_to_cwd(path: Path) -> str:
    return make_path_relative_to(to=Path.cwd(), path=path)


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
    orig_dir = Path.cwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(orig_dir)


def normalise_path_to_str(path: Path) -> str:
    return str(path).replace("\\", "/")


def biguint_bytes_length(value: int) -> int:
    return math.ceil(value.bit_length() / 8.0)


def biguint_bytes_eval(value: int) -> bytes:
    byte_length = biguint_bytes_length(value)
    assert byte_length <= 64, "Biguints must be 64 bytes or less"
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
