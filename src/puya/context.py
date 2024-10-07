from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.models import ContractReference, LogicSigReference
from puya.options import PuyaOptions
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


@attrs.define(kw_only=True)
class CompileContext:
    options: PuyaOptions
    compilation_set: Mapping[ContractReference | LogicSigReference, Path]
    sources_by_path: Mapping[Path, Sequence[str] | None]

    def try_get_source(self, location: SourceLocation | None) -> Sequence[str] | None:
        return try_get_source(self.sources_by_path, location)


def try_get_source(
    sources_by_path: Mapping[Path, Sequence[str] | None], location: SourceLocation | None
) -> Sequence[str] | None:
    if not location or not location.file:
        return None
    source_lines = sources_by_path.get(location.file)
    if source_lines is None:
        return None

    src_content = list(source_lines[location.line - 1 : location.end_line])
    if not src_content:
        logger.warning(f"could not locate source: {location}", location=None)
    else:
        end_column = location.end_column
        if end_column is not None:
            src_content[-1] = src_content[-1][:end_column]
        start_column = location.column
        if start_column is not None:
            src_content[0] = src_content[0][start_column:]
    return src_content
