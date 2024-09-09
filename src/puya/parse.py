from pathlib import Path

import attrs

from puya.utils import make_path_relative_to_cwd


def _resolved_path(p: Path | str) -> Path:
    if isinstance(p, str):
        p = Path(p)
    return p.resolve()


@attrs.frozen(kw_only=True, repr=False, str=False)
class SourceLocation:
    file: Path = attrs.field(converter=_resolved_path)
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
        # TODO: remove .with_comments(), added temporarily to reduce diff
        if self.comment_lines:
            return str(self.with_comments())

        relative_path = make_path_relative_to_cwd(self.file)
        result = f"{relative_path}:{self.line}"
        if self.end_line != self.line:
            result += f"-{self.end_line}"
        return result

    def __repr__(self) -> str:
        # TODO: remove .with_comments(), added temporarily to reduce diff
        if self.comment_lines:
            return repr(self.with_comments())

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

    def __add__(self, other: "SourceLocation | None") -> "SourceLocation":
        if other is None:
            return self

        assert self.file == other.file
        if self.line == other.line:
            start_line = self.line
            start_column = min(
                [c for c in (self.column, other.column) if c is not None], default=None
            )
            # in theory, these should be the same, but no harm in taking the max here
            comment_lines = max(self.comment_lines, other.comment_lines)
        elif self.line < other.line:
            start_line = self.line
            start_column = self.column
            comment_lines = self.comment_lines
        else:
            start_line = other.line
            start_column = other.column
            comment_lines = other.comment_lines

        if self.end_line == other.end_line:
            end_line = self.end_line
            end_column = max(
                [c for c in (self.end_column, other.end_column) if c is not None], default=None
            )
        elif self.end_line > other.end_line:
            end_line = self.end_line
            end_column = self.end_column
        else:
            end_line = other.end_line
            end_column = other.end_column
        return SourceLocation(
            file=self.file,
            line=start_line,
            end_line=end_line,
            column=start_column,
            end_column=end_column,
            comment_lines=comment_lines,
        )
