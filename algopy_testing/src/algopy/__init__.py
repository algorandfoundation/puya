# ruff: noqa: PLC0414
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from algopy_testing.enums import OnCompleteAction, TransactionType
from algopy_testing.models import Account, Application, Asset, Global, Itxn, Txn
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
        self._state: dict[bytes | str, object] = {}

    def __setitem__(self, key: bytes | str, value: object) -> None:
        self._state[key] = value

    def __getitem__(self, key: bytes | str) -> object:
        return self._state[key]


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
    "Itxn",
    "OnCompleteAction",
    "TransactionType",
]
