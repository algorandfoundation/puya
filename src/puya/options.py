from __future__ import annotations

import enum
import typing

import attrs

from puya.algo_constants import MAINNET_TEAL_LANGUAGE_VERSION
from puya.logging_config import LogLevel

if typing.TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class LocalsCoalescingStrategy(enum.StrEnum):
    root_operand = enum.auto()
    root_operand_excluding_args = enum.auto()
    aggressive = enum.auto()


@attrs.define(kw_only=True)
class PuyaOptions:
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    output_teal: bool = True
    output_arc32: bool = True
    output_awst: bool = False
    output_ssa_ir: bool = False
    output_optimization_ir: bool = False
    output_destructured_ir: bool = False
    output_memory_ir: bool = False
    out_dir: Path | None = attrs.field(default=None, repr=False)
    debug_level: int = 1
    optimization_level: int = 1
    log_level: LogLevel = LogLevel.info
    target_avm_version: int = MAINNET_TEAL_LANGUAGE_VERSION
    # TODO: the below is probably not scalable as a set of optimisation on/off flags,
    #       but it'll do for now
    locals_coalescing_strategy: LocalsCoalescingStrategy = LocalsCoalescingStrategy.root_operand
