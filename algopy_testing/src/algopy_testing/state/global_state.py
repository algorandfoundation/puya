from __future__ import annotations

import typing
from typing import cast, overload

_T = typing.TypeVar("_T")


class GlobalState(typing.Generic[_T]):
    @overload
    def __init__(
        self,
        type_: type[_T],
        /,
        *,
        key: bytes | str = "",
        description: str = "",
    ) -> None: ...

    @overload
    def __init__(
        self,
        initial_value: _T,
        /,
        *,
        key: bytes | str = "",
        description: str = "",
    ) -> None: ...

    def __init__(
        self,
        type_or_value: type[_T] | _T,
        /,
        *,
        key: bytes | str = "",
        description: str = "",
    ) -> None:
        if isinstance(type_or_value, type):
            self.type_ = type_or_value
            self._value: _T | None = None
        else:
            self.type_ = type(type_or_value)
            self._value = type_or_value

        self.key = key
        self.description = description

    @property
    def value(self) -> _T:
        if self._value is None:
            raise ValueError("Value is not set")
        return self._value

    @value.setter
    def value(self, value: _T) -> None:
        self._value = value

    @value.deleter
    def value(self) -> None:
        self._value = None

    def __bool__(self) -> bool:
        return self._value is not None

    def get(self, default: _T | None = None) -> _T:
        if self._value is not None:
            return self._value
        if default is not None:
            return default
        return cast(_T, self.type_())

    def maybe(self) -> tuple[_T | None, bool]:
        return self._value, self._value is not None
