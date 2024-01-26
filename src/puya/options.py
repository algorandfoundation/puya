from collections.abc import Sequence
from enum import IntFlag
from pathlib import Path

import attrs

from puya.logging_config import LogLevel


class TealAnnotatorOption(IntFlag):
    op_description = (1 << 0,)
    stack = (1 << 1,)
    vla = (1 << 2,)
    x_stack = (1 << 3,)
    source_info = 1 << 4

    @staticmethod
    def from_string(s: str) -> "TealAnnotatorOption":
        return TealAnnotatorOption(int(s))


@attrs.define(kw_only=True)
class PuyaOptions:
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    output_teal: bool = True
    output_arc32: bool = True
    output_awst: bool = False
    output_ssa_ir: bool = False
    output_optimization_ir: bool = False
    output_cssa_ir: bool = False
    output_post_ssa_ir: bool = False
    output_parallel_copies_ir: bool = False
    output_final_ir: bool = False
    out_dir: Path | None = attrs.field(default=None, repr=False)
    debug_level: int = 0
    optimization_level: int = 0
    log_level: LogLevel = LogLevel.info
    annotations: TealAnnotatorOption | None = None
