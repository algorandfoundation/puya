import contextlib
import contextvars
from collections.abc import Iterator

import attrs

from puya.parse import SourceLocation


@attrs.frozen
class WrapWithSymbol:
    """Indicates that an expression should be wrapped in the specified symbol"""

    symbol: str


@attrs.frozen
class ReplaceWithSymbol:
    """Indicates than an expression should be replaced with the specified symbol"""

    symbol: str


@attrs.frozen
class ReplaceWithMember:
    """
    Indicates that the expression at expr_location should be replaced with the specified member
    """

    expr_location: SourceLocation
    member: str


@attrs.frozen
class DecorateFunction:
    """
    Decorates function with the specified symbol
    """

    symbol: str


CodeEdit = WrapWithSymbol | ReplaceWithSymbol | ReplaceWithMember | DecorateFunction


@attrs.frozen
class CodeFix:
    edit: CodeEdit
    location: SourceLocation


_CODE_FIXES = contextvars.ContextVar[list[CodeFix]]("_CODE_FIXES")


@contextlib.contextmanager
def code_fix_context() -> Iterator[list[CodeFix]]:
    fixes = list[CodeFix]()
    token = _CODE_FIXES.set(fixes)
    try:
        yield fixes
    finally:
        _CODE_FIXES.reset(token)


def suggest_fix(edit: CodeEdit, loc: SourceLocation) -> None:
    try:
        fixes = _CODE_FIXES.get()
    except LookupError:
        pass
    else:
        fixes.append(CodeFix(edit, loc))
