from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict, TypeVar

from algopy_testing.utils import as_int64

if TYPE_CHECKING:
    import algopy


T = TypeVar("T")


class ApplicationFields(TypedDict, total=False):
    approval_program: algopy.Bytes
    clear_state_program: algopy.Bytes
    global_num_uint: algopy.UInt64
    global_num_bytes: algopy.UInt64
    local_num_uint: algopy.UInt64
    local_num_bytes: algopy.UInt64
    extra_program_pages: algopy.UInt64
    creator: algopy.Account
    address: algopy.Account


@dataclass()
class Application:
    id: algopy.UInt64

    def __init__(self, application_id: algopy.UInt64 | int = 0, /):
        from algopy import UInt64

        self.id = application_id if isinstance(application_id, UInt64) else UInt64(application_id)

    def __getattr__(self, name: str) -> typing.Any:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if int(self.id) not in context._application_data:
            raise ValueError(
                "`algopy.Application` is not present in the test context! "
                "Use `context.add_application()` or `context.any_application()` to add the "
                "application to your test setup."
            )

        return_value = context._application_data[int(self.id)].get(name)
        if return_value is None:
            raise AttributeError(
                f"The value for '{name}' in the test context is None. "
                f"Make sure to patch the global field '{name}' using your `AlgopyTestContext` "
                "instance."
            )

        return return_value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Application):
            return self.id == other.id
        return self.id == as_int64(other)

    def __bool__(self) -> bool:
        return self.id != 0

    def __hash__(self) -> int:
        return hash(self.id)
