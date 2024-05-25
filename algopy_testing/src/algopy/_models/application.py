from __future__ import annotations

from typing import TypedDict, TypeVar, cast
from unittest.mock import MagicMock

from algopy._models.account import Account
from algopy._primitives.bytes import Bytes
from algopy._primitives.uint64 import UInt64
from algopy.utils import as_string


class ApplicationOverrides(TypedDict, total=False):
    approval_program: Bytes
    clear_state_program: Bytes
    global_num_uint: UInt64
    global_num_bytes: UInt64
    local_num_uint: UInt64
    local_num_bytes: UInt64
    extra_program_pages: UInt64
    creator: Account
    address: Account


T = TypeVar("T")


class Application:
    _application_id: UInt64

    def __init__(self, application_id: UInt64 | int = 0, /, **overrides: ApplicationOverrides):
        if not isinstance(application_id, UInt64 | int):
            raise TypeError("Invalid value for Application ID")
        self._application_id = (
            application_id if isinstance(application_id, UInt64) else UInt64(application_id)
        )
        self._overrides = overrides

    def __eq__(self, other: object) -> bool:
        return self._application_id == as_string(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self._application_id != 0

    @property
    def id(self) -> UInt64:
        return self._application_id

    def _get_property(self, name: str, default: T) -> T:
        return cast(T, self._overrides.get(name, default))

    @property
    def approval_program(self) -> Bytes:
        return self._get_property("approval_program", MagicMock(spec=Bytes))

    @property
    def clear_state_program(self) -> Bytes:
        return self._get_property("clear_state_program", MagicMock(spec=Bytes))

    @property
    def global_num_uint(self) -> UInt64:
        return self._get_property("global_num_uint", MagicMock(spec=UInt64))

    @property
    def global_num_bytes(self) -> UInt64:
        return self._get_property("global_num_bytes", MagicMock(spec=UInt64))

    @property
    def local_num_uint(self) -> UInt64:
        return self._get_property("local_num_uint", MagicMock(spec=UInt64))

    @property
    def local_num_bytes(self) -> UInt64:
        return self._get_property("local_num_bytes", MagicMock(spec=UInt64))

    @property
    def extra_program_pages(self) -> UInt64:
        return self._get_property("extra_program_pages", MagicMock(spec=UInt64))

    @property
    def creator(self) -> Account:
        return self._get_property("creator", MagicMock(spec=Account))

    @property
    def address(self) -> Account:
        return self._get_property("address", MagicMock(spec=Account))
