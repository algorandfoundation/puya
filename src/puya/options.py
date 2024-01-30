from collections.abc import Sequence
from pathlib import Path

import attrs

from puya.algo_constants import MAINNET_TEAL_LANGUAGE_VERSION
from puya.logging_config import LogLevel


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
    target_avm_version: int = MAINNET_TEAL_LANGUAGE_VERSION
