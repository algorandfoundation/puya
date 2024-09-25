import contextlib
from collections.abc import Iterator

import attrs

from puya.errors import InternalError


@attrs.define
class AlignedWriter:
    _headers: list[str] = attrs.field(factory=list)
    _lines: list[list[str] | str] = attrs.field(factory=list)
    _current_line: list[str] = attrs.field(factory=list)
    _ignore_current_line: bool = False
    _padding: dict[int, int] = attrs.field(factory=dict)
    _indent: str = ""
    omit_empty_columns: bool = True

    @property
    def ignore_current_line(self) -> bool:
        return self._ignore_current_line

    @property
    def current_indent(self) -> str:
        return self._indent

    @contextlib.contextmanager
    def indent(self) -> Iterator[None]:
        indent_width = 4
        original_indent = self._indent
        self._indent += " " * indent_width
        try:
            yield
        finally:
            self._indent = original_indent

    def add_header(self, header: str, padding: int = 1) -> None:
        self._padding[len(self._headers)] = padding
        self._headers.append(header)

    def append(self, part: str) -> None:
        self._current_line.append(part)

    def new_line(self) -> None:
        parts = self._current_line
        if not self._ignore_current_line:
            if parts and self._indent:
                parts[0] = f"{self._indent}{parts[0]}"
            self._lines.append(parts)
        self._ignore_current_line = False
        self._current_line = []

    def append_line(self, line: str) -> None:
        if self._current_line or self._ignore_current_line:
            raise InternalError(
                "Cannot append a new line while a current line is in progress, missing new_line()?"
            )
        self._lines.append(line)

    def ignore_line(self) -> None:
        self._ignore_current_line = True

    def _join_columns(self, line: list[str], widths: dict[int, int]) -> str:
        return "".join(
            part.ljust(widths.get(column, 0))
            for column, part in enumerate(line)
            if widths.get(column, 0) or not self.omit_empty_columns
        ).rstrip()

    def write(self) -> list[str]:
        widths = dict[int, int]()
        all_lines = self._lines.copy()
        for parts in all_lines:
            if isinstance(parts, list):
                for column, part in enumerate(parts):
                    widths[column] = max(widths.get(column, 0), len(part))

        for column, width in widths.items():
            if width == 0 and self.omit_empty_columns:
                continue
            if column < len(self._headers):
                width = max(width, len(self._headers[column]))
            widths[column] = width + self._padding.get(column, 1)

        if self._headers:
            all_lines.insert(0, self._headers)

        return [
            line if isinstance(line, str) else self._join_columns(line, widths)
            for line in all_lines
        ]
