import contextlib
import functools
import math
import os
from collections.abc import Callable, Iterable, MutableMapping, MutableSet, Set
from pathlib import Path
from typing import Any, Iterator, Self, TypeGuard, TypeVar

import attrs

from puya.options import PuyaOptions

T_A = TypeVar("T_A", bound=attrs.AttrsInstance)


def sha512_256_hash(value: bytes) -> bytes:
    """
    Returns the SHA512/256 hash of a value. This is the hashing algorithm used
    to generate address checksums
    """
    from Cryptodome.Hash import SHA512

    sha = SHA512.new(truncate="256")
    sha.update(value)
    return sha.digest()


def attrs_extend(new_type: type[T_A], base_instance: Any, **changes: Any) -> T_A:  # noqa: ANN401
    """Like attrs.evolve but allows creating a sub-type"""
    base_type = type(base_instance)
    assert issubclass(new_type, base_type)
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


T = TypeVar("T")


def no_none_in_list(lst: list[T | None]) -> TypeGuard[list[T]]:
    return None not in lst


def no_none_in_tuple(tup: tuple[T | None, ...]) -> TypeGuard[tuple[T, ...]]:
    return None not in tup


@functools.cache
def make_path_relative(*, to: Path, path: str) -> str:
    with contextlib.suppress(ValueError):
        path = str(Path(path).relative_to(to))
    return path.replace(os.sep, "/")


def make_path_relative_to_cwd(path: str | Path) -> str:
    return make_path_relative(to=Path.cwd(), path=str(path))


def unique(items: Iterable[T]) -> list[T]:
    return list(dict.fromkeys(items))


class StableSet(MutableSet[T]):
    __slots__ = ("_data",)

    def __init__(self, *items: T) -> None:
        self._data = dict.fromkeys(items)

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

    def __or__(self, other: Iterable[T]) -> "StableSet[T]":  # type: ignore[override]
        result = StableSet.__new__(StableSet)
        if isinstance(other, StableSet):
            other_data = other._data
        else:
            other_data = dict.fromkeys(other)
        result._data = self._data | other_data
        return result

    def __ior__(self, other: Iterable[T]) -> Self:  # type: ignore[override]
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

    def __repr__(self) -> str:
        return type(self).__name__ + "(" + ", ".join(map(repr, self._data)) + ")"


def determine_out_dir(contract_path: Path, options: PuyaOptions) -> Path:
    if options.out_dir:
        # find input path the contract is relative to
        for src_path in options.paths:
            src_path = src_path.resolve()
            src_path = src_path if src_path.is_dir() else src_path.parent
            try:
                relative_path = contract_path.relative_to(src_path)
            except ValueError:
                continue
            # construct a path that maintains a hierarchy to src_path
            out_dir = options.out_dir / relative_path
            if not options.out_dir.is_absolute():
                out_dir = src_path / out_dir
            break
        else:
            # if not relative to any input path
            if options.out_dir.is_absolute():
                out_dir = options.out_dir / contract_path
            else:
                out_dir = contract_path / options.out_dir
    else:
        out_dir = contract_path

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


U = TypeVar("U")


def lazy_setdefault(m: MutableMapping[T, U], /, key: T, default: Callable[[T], U]) -> U:
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
