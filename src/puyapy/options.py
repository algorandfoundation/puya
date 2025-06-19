from collections.abc import Sequence
from pathlib import Path

import attrs

from puya.log import LogLevel
from puya.options import PuyaOptions


@attrs.frozen(kw_only=True)
class PuyaPyOptions(PuyaOptions):
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    output_awst: bool = False
    output_awst_json: bool = False
    output_source_annotations_json: bool = False
    output_client: bool = False
    out_dir: Path | None = attrs.field(default=None, repr=False)
    log_level: LogLevel = LogLevel.info
