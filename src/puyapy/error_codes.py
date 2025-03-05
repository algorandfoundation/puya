# ruff: noqa: N802
import attrs

from puya.errors import ContextErrorData
from puya.parse import SourceLocation


@attrs.frozen
class TypeErrorContext:
    type: str


def INVALID_LITERAL(typ: str, loc: SourceLocation) -> ContextErrorData[TypeErrorContext]:
    return ContextErrorData(
        severity="error",
        code="invalid-literal",
        message="a Python literal is not valid at this location",
        context=TypeErrorContext(type=typ),
        location=loc,
    )


@attrs.frozen
class LenUnsupportedContext:
    expr: SourceLocation


def LEN_UNSUPPORTED(loc: SourceLocation) -> ContextErrorData[LenUnsupportedContext]:
    # TODO: this doesn't work if len has been aliased to something else...
    assert loc.column is not None, "expected column to be set"
    assert loc.end_column is not None, "expected end_column to be set"
    expr_loc = attrs.evolve(loc, column=loc.column + 3, end_column=loc.end_column - 1)
    return ContextErrorData(
        severity="error",
        code="len-unsupported",
        message="len() is not supported"
        " - types with a length will have a .length property instead",
        context=LenUnsupportedContext(expr=expr_loc),
        location=loc,
    )


@attrs.frozen
class UnsupportedContext:
    unsupported: SourceLocation
    replacement: str


def RANGE_UNSUPPORTED(loc: SourceLocation) -> ContextErrorData[UnsupportedContext]:
    # TODO: this doesn't work if range has been aliased to something else...
    assert loc.column is not None, "expected column to be set"
    expr_loc = attrs.evolve(loc, end_column=loc.column + len("range"), end_line=loc.line)
    return ContextErrorData(
        severity="error",
        code="unsupported",
        message="range() is not supported - use algopy.urange() instead",
        context=UnsupportedContext(unsupported=expr_loc, replacement="algopy.urange"),
        location=loc,
    )


def ENUMERATE_UNSUPPORTED(loc: SourceLocation) -> ContextErrorData[UnsupportedContext]:
    # TODO: this doesn't work if range has been aliased to something else...
    assert loc.column is not None, "expected column to be set"
    expr_loc = attrs.evolve(loc, end_column=loc.column + len("enumerate"), end_line=loc.line)
    return ContextErrorData(
        severity="error",
        code="unsupported",
        message="enumerate() is not supported - use algopy.uenumerate() instead",
        context=UnsupportedContext(unsupported=expr_loc, replacement="algopy.uenumerate"),
        location=loc,
    )
