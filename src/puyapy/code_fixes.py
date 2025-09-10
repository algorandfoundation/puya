from collections.abc import Sequence

import attrs

from puya.errors import CodeError
from puya.parse import SourceLocation


@attrs.frozen
class WrapWithSymbol:
    """Indicates that an expression should be wrapped in the specified symbol"""

    symbol: str


@attrs.frozen
class ReplaceWithSymbol:
    """Indicates that an expression should be replaced with the specified symbol"""

    symbol: str


@attrs.frozen
class DecorateFunction:
    """
    Decorates function with the specified symbol
    """

    symbol: str


CodeEdit = WrapWithSymbol | ReplaceWithSymbol | DecorateFunction


@attrs.frozen
class CodeFix:
    edit: CodeEdit
    location: SourceLocation


class FixableCodeError(CodeError):
    def __init__(
        self,
        msg: str,
        location: SourceLocation,
        edits: CodeEdit | Sequence[CodeEdit],
    ):
        super().__init__(msg, location)
        self.edits = edits
