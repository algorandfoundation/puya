# ruff: noqa: PLC0414
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from algopy_testing.arc4 import ARC4Contract
from algopy_testing.enums import OnCompleteAction, TransactionType
from algopy_testing.models import Account, Application, Asset, Contract, Global, ITxn, Txn
from algopy_testing.primitives import BigUInt, Bytes, String, UInt64
from algopy_testing.state.local_state import LocalState

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
    "Contract",
    "ARC4Contract",
    "Global",
    "LocalState",
    "Txn",
    "subroutine",
    "ITxn",
    "OnCompleteAction",
    "TransactionType",
]
