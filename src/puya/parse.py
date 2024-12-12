import functools
import typing
from collections.abc import Iterable
from pathlib import Path

import attrs

from puya.utils import make_path_relative_to_cwd


@attrs.frozen(kw_only=True, repr=False, str=False)
class SourceLocation:
    file: Path | None = attrs.field()
    line: int = attrs.field(validator=attrs.validators.ge(1))
    end_line: int = attrs.field()
    comment_lines: int = attrs.field(default=0, validator=attrs.validators.ge(0))
    """the number of lines preceding `line` to take as a comment"""
    column: int | None = attrs.field(
        default=None, validator=attrs.validators.optional(attrs.validators.ge(0))
    )
    end_column: int | None = attrs.field(
        default=None, validator=attrs.validators.optional(attrs.validators.ge(1))
    )

    @file.validator
    def _file_validator(self, _attribute: object, value: Path) -> None:
        # this check is simply to make sure relative paths aren't accidentally passed in.
        # so we use root rather than is_absolute(), because that requires a drive on Windows,
        # which we naturally don't supply for synthetic paths such as embedded lib.
        if value is not None and not value.root:
            raise ValueError(f"source file locations cannot be relative, got {value}")

    @end_line.default
    def _end_line_default(self) -> int:
        return self.line

    @end_line.validator
    def _end_line_validator(self, _attribute: object, value: int) -> None:
        if value < self.line:
            raise ValueError(f"end_line = {value} is before start line = {self.line}")

    @end_column.validator
    def _end_column_validator(self, _attribute: object, value: int | None) -> None:
        if (
            self.end_line == self.line
            and value is not None
            and self.column is not None
            and value <= self.column
        ):
            raise ValueError(
                f"source location end column = {value} is before start column = {self.column}"
            )

    @property
    def line_count(self) -> int:
        return self.end_line - self.line + 1

    def __str__(self) -> str:
        relative_path = make_path_relative_to_cwd(self.file) if self.file else "INTERNAL"
        result = f"{relative_path}:{self.line}"
        if self.end_line != self.line:
            result += f"-{self.end_line}"
        return result

    def __repr__(self) -> str:
        result = str(self)
        if self.column is not None:
            result += f":{self.column}"
            if self.end_column is not None:
                result += f"-{self.end_column}"
        return result

    def with_comments(self) -> "SourceLocation":
        if self.comment_lines == 0:
            return self
        return attrs.evolve(
            self,
            line=self.line - self.comment_lines,
            column=None,
            comment_lines=0,
        )

    def try_merge(self, other: "SourceLocation | None") -> "SourceLocation":
        """Attempt to merge this source location with another, if they are either adjacent
        or overlapping in lines. If not, the source location is returned unmodified."""
        if other is None or other.file != self.file:
            return self
        file = self.file
        # if they both start at the same line, not only is there overlap,
        # but things are also much simpler
        if self.line == other.line:
            line = self.line
            # expand to the largest end_line
            end_line = max(self.end_line, other.end_line)
            # in theory this should be the same value, but just in case, we can take the max
            comment_lines = max(self.comment_lines, other.comment_lines)
            # if either location is not column-bounded, then the result shouldn't be either
            # otherwise take the minimum of the columns, since the line numbers are the same
            if self.column is None or other.column is None:
                column = None
            else:
                column = min(self.column, other.column)
        else:
            # if they don't start on the same line, one must start first
            first, second = (self, other) if self.line < other.line else (other, self)
            line_after_first = first.end_line + 1
            # TODO: maybe consider fetching the source to exclude blank lines?
            if line_after_first < second.line:
                return self
            # first starts first, so... that's where we start
            line = first.line
            # whilst we know first starts before second,
            # it's also possible that first ends after second
            end_line = max(second.end_line, first.end_line)
            # naturally, comment line count needs to come from the first location
            comment_lines = first.comment_lines
            # same first starting column
            column = first.column
        # the logic for computing the end_column is the same regardless of whether
        # they start on the same line or not
        if self.end_line == other.end_line:
            # if either location is not end_column-bounded, then the result shouldn't be either
            # otherwise take the maximum of the end_columns, since the line numbers are the same
            if self.end_column is None or other.end_column is None:
                end_column = None
            else:
                end_column = max(self.end_column, other.end_column)
        elif self.end_line > other.end_line:
            # if self ends last, take it's end column
            end_column = self.end_column
        else:
            # otherwise other ends last, so take it's end column
            end_column = other.end_column

        return SourceLocation(
            file=file,
            line=line,
            end_line=end_line,
            comment_lines=comment_lines,
            column=column,
            end_column=end_column,
        )


@typing.overload
def sequential_source_locations_merge(sources: Iterable[SourceLocation]) -> SourceLocation: ...


@typing.overload
def sequential_source_locations_merge(
    sources: Iterable[SourceLocation | None],
) -> SourceLocation | None: ...


def sequential_source_locations_merge(
    sources: Iterable[SourceLocation | None],
) -> SourceLocation | None:
    """Given a sequence of SourceLocations, try merging them one at a one in order.

    If all sources are None, then None is returned.

    If there are no sources, then a TypeError will be raised.
    """
    return functools.reduce(_try_merge_source_locations, sources)


def _try_merge_source_locations(
    source: SourceLocation | None, merge: SourceLocation | None
) -> SourceLocation | None:
    if source is None:
        return merge
    return source.try_merge(merge)
