import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TestContext(Generic[T]):
    _thread_local = threading.local()

    def __new__(cls, *args: Any, **kwargs: Any) -> "TestContext[T]":
        instance = cls._thread_local.__dict__.get(cls.__name__)
        if instance is None:
            instance = super().__new__(cls, *args, **kwargs)
            instance.init()
            cls._thread_local.__dict__[cls.__name__] = instance
        return instance

    def init(self) -> None:
        self.state: dict[str, T] = {}

    def reset(self) -> None:
        self.state = {}

    def update_state(self, key: str, value: T) -> None:
        self.state[key] = value

    def get_state(self, key: str, default: T | None = None) -> T | None:
        return self.state.get(key, default)


@contextmanager
def state_context() -> Generator[TestContext[Any], None, None]:
    """
    Context manager for blockchain test context, for use in unit tests.
    """

    state = TestContext[Any]()

    try:
        yield state
    finally:
        state.reset()
