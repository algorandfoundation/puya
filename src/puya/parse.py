import sys
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
    line: int
    end_line: int = attrs.field()
    # TODO: much better validation below
    column: int | None = None
    end_column: int | None = None

    @end_line.default
    def _end_line_default(self) -> int:
        return self.line

    @end_line.validator
    def _end_line_validator(self, _attribute: object, value: int) -> None:
        if value < self.line:
            raise ValueError(f"end_line = {value} is before start line = {self.line}")

    def __str__(self) -> str:
        relative_path = make_path_relative_to_cwd(self.file)
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

    def __add__(self, other: "SourceLocation | None") -> "SourceLocation":
        if other is None:
            return self

        assert self.file == other.file
        lines = [self.line, other.line, self.end_line, other.end_line]
        start_line = min(lines)
        end_line = max(lines)
        columns = [
            (self.line, self.column),
            (self.end_line, self.end_column),
            (other.line, other.column),
            (other.end_line, other.end_column),
        ]
        start_column = sys.maxsize
        end_column = -1
        for line, column in columns:
            if column is not None:
                if line == start_line:
                    start_column = min(start_column, column)
                elif line == end_line:
                    end_column = max(end_column, column)
        return SourceLocation(
            file=self.file,
            line=start_line,
            end_line=end_line,
            column=None if start_column == sys.maxsize else start_column,
            end_column=None if end_column == -1 else end_column,
        )
