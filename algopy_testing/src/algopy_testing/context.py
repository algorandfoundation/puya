import dataclasses
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar


@dataclasses.dataclass
class TestingContext:
    program_bytes: bytes | None = None


_var = ContextVar[TestingContext]("_var")


def get_active_context() -> TestingContext:
    return _var.get()


@contextmanager
def new_context() -> Generator[TestingContext, None, None]:
    token = _var.set(TestingContext())
    try:
        yield _var.get()
    finally:
        _var.reset(token)
