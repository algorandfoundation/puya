from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


@contextmanager
def state_context(contextvars: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    tokens = {}
    variables = {}
    try:
        for key, value in contextvars.items():
            var: ContextVar[Any] = ContextVar(key)
            tokens[key] = var.set(value)
            variables[key] = var
        yield contextvars
    finally:
        for key, token in tokens.items():
            var = variables[key]
            var.reset(token)
