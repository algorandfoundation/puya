# ruff: noqa: N802
from collections.abc import Callable

import attrs

from puya.errors import ErrorData
from puya.parse import SourceLocation

# region fixes
@attrs.frozen
class WrapWithSymbol:
    symbol: str


@attrs.frozen
class ReplaceWithSymbol:
    symbol: str


@attrs.frozen
class ReplaceWithMember:
    expr_location: SourceLocation
    member: str
# endregion

# region helper functions
def _error(*, code: str, message: str, loc: SourceLocation, fix: object = None) -> ErrorData:
    return ErrorData(
        severity="error",
        code=code,
        message=message,
        fix=fix,
        location=loc,
    )


def _error_factory(
    *, code: str, message: str, fix: object = None
) -> Callable[[SourceLocation], ErrorData]:
    def factory(loc: SourceLocation) -> ErrorData:
        return _error(
            code=code,
            message=message,
            fix=fix,
            loc=loc,
        )

    return factory
# endregion

# region error definitions
INVALID_LITERAL_INT = _error_factory(
    code="0000",
    message="a Python literal is not valid at this location",
    fix=WrapWithSymbol("algopy.UInt64"),
)
INVALID_LITERAL_BYTES = _error_factory(
    code="0000",
    message="a Python literal is not valid at this location",
    fix=WrapWithSymbol("algopy.Bytes"),
)
INVALID_LITERAL_STR = _error_factory(
    code="0000",
    message="a Python literal is not valid at this location",
    fix=WrapWithSymbol("algopy.String"),
)
INVALID_LITERAL_NO_FIX = _error_factory(
    code="0000",
    message="a Python literal is not valid at this location",
)
LEN_UNSUPPORTED = _error_factory(
    code="0000",
    message="len() is not supported - types with a length will have a .length property instead",
)
RANGE_UNSUPPORTED = _error_factory(
    code="0000",
    message="range() is not supported - use algopy.urange() instead",
    fix=ReplaceWithSymbol("algopy.urange"),
)
ENUMERATE_UNSUPPORTED = _error_factory(
    code="0000",
    message="enumerate() is not supported - use algopy.uenumerate() instead",
    fix=ReplaceWithSymbol("algopy.uenumerate"),
)

_INVALID_LITERALS = {
    "builtins.int": INVALID_LITERAL_INT,
    "builtins.bytes": INVALID_LITERAL_BYTES,
    "builtins.str": INVALID_LITERAL_STR,
}


def INVALID_LITERAL(typ: str, loc: SourceLocation) -> ErrorData:
    factory = _INVALID_LITERALS.get(typ, INVALID_LITERAL_NO_FIX)
    return factory(loc)
#endregion
