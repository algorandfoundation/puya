import enum
from collections.abc import Mapping
from functools import cached_property

import attrs

from puya.algo_constants import MAINNET_TEAL_LANGUAGE_VERSION


class LocalsCoalescingStrategy(enum.StrEnum):
    root_operand = enum.auto()
    root_operand_excluding_args = enum.auto()
    aggressive = enum.auto()


@attrs.define(kw_only=True)
class PuyaOptions:
    output_teal: bool = True
    output_arc32: bool = True
    output_ssa_ir: bool = False
    output_optimization_ir: bool = False
    output_destructured_ir: bool = False
    output_memory_ir: bool = False
    output_bytecode: bool = False
    match_algod_bytecode: bool = False
    debug_level: int = 1
    optimization_level: int = 1
    target_avm_version: int = MAINNET_TEAL_LANGUAGE_VERSION
    cli_template_definitions: Mapping[str, int | bytes] = attrs.field(factory=dict)
    template_vars_prefix: str = "TMPL_"
    # TODO: the below is probably not scalable as a set of optimisation on/off flags,
    #       but it'll do for now
    locals_coalescing_strategy: LocalsCoalescingStrategy = LocalsCoalescingStrategy.root_operand

    @cached_property
    def template_variables(self) -> Mapping[str, int | bytes]:
        return {self.template_vars_prefix + k: v for k, v in self.cli_template_definitions.items()}
