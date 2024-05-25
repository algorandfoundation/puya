# ruff: noqa: PLC0414
import typing
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from algopy._enums import OnCompleteAction, TransactionType
from algopy._models import Account, Application, Asset, Global, Itxn, Txn
from algopy._primitives.biguint import BigUInt as BigUInt
from algopy._primitives.bytes import Bytes as Bytes
from algopy._primitives.string import String as String
from algopy._primitives.uint64 import UInt64 as UInt64


class ARC4Contract:
    pass


_TState = typing.TypeVar("_TState")


class LocalState:
    def __init__(
        self,
        type_: type[_TState],
        /,
        *,
        key: bytes | str = ...,
        description: str = "",
    ) -> None:
        pass


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
