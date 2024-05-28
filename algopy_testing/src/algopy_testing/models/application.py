from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from algopy_testing.utils import as_string

if TYPE_CHECKING:
    from algopy_testing.models.account import Account
    from algopy_testing.primitives.bytes import Bytes
from algopy_testing.primitives.uint64 import UInt64

T = TypeVar("T")


@dataclass
class Application:
    id: UInt64 | None = None
    approval_program: Bytes | None = None
    clear_state_program: Bytes | None = None
    global_num_uint: UInt64 | None = None
    global_num_bytes: UInt64 | None = None
    local_num_uint: UInt64 | None = None
    local_num_bytes: UInt64 | None = None
    extra_program_pages: UInt64 | None = None
    creator: Account | None = None
    address: Account | None = None

    def __init__(self, application_id: UInt64 | int = 0, /):
        self.id = application_id if isinstance(application_id, UInt64) else UInt64(application_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Application):
            return self.id == other.id
        return self.id == as_string(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        return self.id != 0
