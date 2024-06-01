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

    def __setitem__(self, key: object, value: object) -> None:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        self._state[key] = value

    def __getitem__(self, key: object) -> object:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        return self._state[key]

    def __delitem__(self, key: object) -> None:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        del self._state[key]

    def __contains__(self, key: object) -> bool:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        return key in self._state

    def get(self, key: object, default: object = None) -> object:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        return self._state.get(key, default)

    def maybe(self, key: object) -> tuple[object, bool]:
        from algopy import Account, Application, Asset

        if isinstance(key, Account):
            key = str(key)
        elif isinstance(key, Application | Asset):
            key = key.id.value if key.id else None
        value = self._state.get(key)
        return value, key in self._state


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
