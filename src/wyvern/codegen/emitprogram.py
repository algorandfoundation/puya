from collections.abc import Sequence

import attrs
import structlog

from wyvern.ir import models

logger = structlog.get_logger(__file__)


@attrs.define(kw_only=True)
class CompiledProgram:
    src: list[str]
    debug_src: list[str] | None


@attrs.define(kw_only=True)
class CompiledContract:
    name: str
    approval_program: CompiledProgram
    """lines of the TEAL approval program for the contract"""
    clear_program: CompiledProgram
    """lines of the TEAL clear program for the contract"""

    # metadata fields below
    description: str | None
    name_override: str | None
    # TODO: either put ContractState type somewhere common or copy to here
    global_state: Sequence[models.ContractState]
    local_state: Sequence[models.ContractState]
