# ruff: noqa: PLC0414
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from algopy_testing.enums import OnCompleteAction, TransactionType
from algopy_testing.models import Account, Application, Asset, Global, ITxn, Txn
from algopy_testing.primitives import BigUInt, Bytes, String, UInt64


# TODO: Refine further, currently simplified to limit the scope of state management abstractions PR
class ARC4Contract:
    pass


# TODO: Refine further, currently simplified to limit the scope of state management abstractions PR
class LocalState:
    def __init__(
        self,
        type_: type[object],
        /,
        *,
        key: bytes | str = "",
        description: str = "",
    ) -> None:
        self.type_ = type_
        self.key = key
        self.description = description
        self._state: dict[object, object] = {}

    def _validate_local_state_key(self, key: Account | UInt64 | int) -> None:
        if not isinstance(key, Account | UInt64 | int):
            raise TypeError(f"Invalid key type {type(key)} for LocalState")

    def __setitem__(self, key: Account | UInt64 | int, value: object) -> None:
        self._validate_local_state_key(key)
        self._state[key] = value

    def __getitem__(self, key: Account | UInt64 | int) -> object:
        self._validate_local_state_key(key)
        return self._state[key]

    def __delitem__(self, key: Account | UInt64 | int) -> None:
        self._validate_local_state_key(key)
        del self._state[key]

    def __contains__(self, key: Account | UInt64 | int) -> bool:
        self._validate_local_state_key(key)
        return key in self._state

    def get(self, key: Account | UInt64 | int, default: object = None) -> object:
        self._validate_local_state_key(key)
        return self._state.get(key, default)

    def maybe(self, key: Account | UInt64 | int) -> tuple[object, bool]:
        self._validate_local_state_key(key)
        return self._state.get(key), key in self._state


_P = ParamSpec("_P")
_R = TypeVar("_R")


def subroutine(sub: Callable[_P, _R]) -> Callable[_P, _R]:
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return sub(*args, **kwargs)

    return wrapped


__all__ = [
    "Account",
    "Application",
    "Asset",
    "Bytes",
    "String",
    "UInt64",
    "BigUInt",
    "ARC4Contract",
    "Global",
    "LocalState",
    "Txn",
    "subroutine",
    "ITxn",
    "OnCompleteAction",
    "TransactionType",
]
