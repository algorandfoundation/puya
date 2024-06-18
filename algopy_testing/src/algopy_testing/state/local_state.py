from __future__ import annotations

import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import algopy

_T = typing.TypeVar("_T")


class LocalState(typing.Generic[_T]):
    def __init__(
        self,
        type_: type[_T],
        /,
        *,
        key: bytes | str = "",
        description: str = "",
    ) -> None:
        self.type_ = type_
        self.key = key
        self.description = description
        self._state: dict[object, _T] = {}

    def _validate_local_state_key(self, key: algopy.Account | algopy.UInt64 | int) -> None:
        from algopy import Account, UInt64

        if not isinstance(key, Account | UInt64 | int):
            raise TypeError(f"Invalid key type {type(key)} for LocalState")

    def __setitem__(self, key: algopy.Account | algopy.UInt64 | int, value: _T) -> None:
        self._validate_local_state_key(key)
        self._state[key] = value

    def __getitem__(self, key: algopy.Account | algopy.UInt64 | int) -> _T:
        self._validate_local_state_key(key)
        return self._state[key]

    def __delitem__(self, key: algopy.Account | algopy.UInt64 | int) -> None:
        self._validate_local_state_key(key)
        del self._state[key]

    def __contains__(self, key: algopy.Account | algopy.UInt64 | int) -> bool:
        self._validate_local_state_key(key)
        return key in self._state

    def get(self, key: algopy.Account | algopy.UInt64 | int, default: _T | None = None) -> _T:
        self._validate_local_state_key(key)
        return self._state.get(key, default if default is not None else self.type_())

    def maybe(self, key: algopy.Account | algopy.UInt64 | int) -> tuple[object, bool]:
        self._validate_local_state_key(key)
        return self._state.get(key), key in self._state
