import attrs
import structlog

from puya.metadata import ContractMetaData

logger = structlog.get_logger(__file__)


@attrs.define(kw_only=True)
class CompiledProgram:
    src: list[str]
    debug_src: list[str] | None


@attrs.define(kw_only=True)
class CompiledContract:
    approval_program: CompiledProgram
    """lines of the TEAL approval program for the contract"""
    clear_program: CompiledProgram
    """lines of the TEAL clear program for the contract"""
    metadata: ContractMetaData
