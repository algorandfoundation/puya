import attrs

from puya.context import CompileContext
from puya.parse import SourceLocation


@attrs.frozen
class SourceMeta:
    location: str | None
    code: list[str] | None


_EmptyMeta = SourceMeta(None, None)


class SourceMetaRetriever:
    def __init__(self, context: CompileContext):
        self.context = context

    def try_get_source(self, location: SourceLocation | None) -> SourceMeta:
        if location is None:
            return _EmptyMeta
        source_lines = self.context.read_source(location.file)
        if not source_lines:
            src_content = list[str]()
        else:
            start_line = end_line = location.line
            if location.end_line:
                end_line = location.end_line
            src_content = source_lines[start_line - 1 : end_line]  # location.lines is one-indexed

            start_column = location.column
            end_column = location.end_column
            if start_line == end_line and start_column is not None and end_column is not None:
                src_content[0] = src_content[0][start_column:end_column]
            else:
                if start_column is not None:
                    src_content[0] = src_content[0][start_column:]
                if end_column is not None:
                    src_content[-1] = src_content[-1][:end_column]
        return SourceMeta(location=location.clickable_str, code=src_content)
