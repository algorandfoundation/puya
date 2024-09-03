from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.models import ContractReference, LogicSigReference
from puya.options import PuyaOptions
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


@attrs.frozen
class SourceMeta:
    location: str | None
    code: Sequence[str] | None


@attrs.define(kw_only=True)
class CompileContext:
    options: PuyaOptions
    compilation_set: Mapping[ContractReference | LogicSigReference, Path]
    sources_by_path: Mapping[Path, Sequence[str] | None]

    def try_get_source(self, location: SourceLocation | None) -> SourceMeta | None:
        return try_get_source(self.sources_by_path, location)


def try_get_source(
    sources_by_path: Mapping[Path, Sequence[str] | None], location: SourceLocation | None
) -> SourceMeta | None:
    if location is None or location.line < 0:
        return None
    source_lines = sources_by_path.get(location.file)
    if not source_lines:
        src_content = list[str]()
    else:
        start_line = end_line = location.line
        if location.end_line:
            end_line = location.end_line
        src_content = list(
            source_lines[start_line - 1 : end_line]  # location.lines is one-indexed
        )

        start_column = location.column
        end_column = location.end_column
        if not src_content:
            logger.warning(f"Could not locate source: {location}", location=None)
        elif start_line == end_line and start_column is not None and end_column is not None:
            src_content[0] = src_content[0][start_column:end_column]
        else:
            if start_column is not None:
                src_content[0] = src_content[0][start_column:]
            if end_column is not None:
                src_content[-1] = src_content[-1][:end_column]
    return SourceMeta(location=str(location), code=src_content)
