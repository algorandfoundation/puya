from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from puya.log import LogLevel
from puya.options import PuyaOptions


@attrs.frozen(kw_only=True)
class PuyaPyOptions(PuyaOptions):
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    sources: Mapping[Path, str] = attrs.field(factory=dict)

    output_awst: bool = False
    output_awst_json: bool = False
    output_client: bool = False
    out_dir: Path | None = attrs.field(default=None, repr=False)
    log_level: LogLevel = LogLevel.info
    prefix: Path | None = None
