# ruff: noqa: PLC0414
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from algopy_testing.enums import OnCompleteAction, TransactionType
from algopy_testing.models import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    Contract,
    Global,
    GTxn,
    ITxn,
    Txn,
)
from algopy_testing.primitives import BigUInt, Bytes, String, UInt64
from algopy_testing.state import GlobalState, LocalState

_P = ParamSpec("_P")
_R = TypeVar("_R")


def subroutine(sub: Callable[_P, _R]) -> Callable[_P, _R]:
    return sub


__all__ = [
    "ARC4Contract",
    "Account",
    "Application",
    "Asset",
    "BigUInt",
    "Bytes",
    "Contract",
    "Global",
    "GlobalState",
    "GTxn",
    "ITxn",
    "LocalState",
    "OnCompleteAction",
    "String",
    "TransactionType",
    "Txn",
    "UInt64",
    "subroutine",
]
