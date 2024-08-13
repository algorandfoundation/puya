from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import attrs

from puya.utils import make_path_relative_to_cwd


@attrs.frozen
class ParseSource:
    path: Path
    module_name: str
    is_explicit: bool
    lines: Sequence[str] | None


@attrs.frozen(kw_only=True, repr=False, str=False)
class SourceLocation:
    file: str
    line: int
    # TODO: much better validation below
    end_line: int | None = None
    column: int | None = None
    end_column: int | None = None

    def __str__(self) -> str:
        relative_path = make_path_relative_to_cwd(self.file)
        result = f"{relative_path}:{self.line}"
        if self.end_line is not None and self.end_line != self.line:
            result += f"-{self.end_line}"
        return result

    def __repr__(self) -> str:
        result = str(self)
        if self.column is not None:
            result += f":{self.column}"
            if self.end_column is not None:
                result += f"-{self.end_column}"
        return result

    def __add__(self, other: SourceLocation | None) -> SourceLocation:
        if other is None:
            return self

        assert self.file == other.file
        lines = list(filter(None, (self.line, other.line, self.end_line, other.end_line)))
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
