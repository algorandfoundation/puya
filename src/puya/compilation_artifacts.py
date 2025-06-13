import abc
import typing
from collections.abc import Mapping, Sequence

import attrs

from puya.artifact_metadata import ContractMetaData, LogicSignatureMetaData
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference

TemplateValue = tuple[int | bytes, SourceLocation | None]


class DebugEvent(typing.TypedDict, total=False):
    """Describes various attributes for a particular PC location"""

    subroutine: str
    """Subroutine name"""
    params: Mapping[str, str]
    """Describes a subroutines parameters and their types"""
    block: str
    """Name of a block"""
    stack_in: Sequence[str]
    """Variable names on the stack BEFORE the next op executes"""
    op: str
    """Op description"""
    callsub: str
    """The subroutine that is about to be called"""
    retsub: bool
    """Returns from current subroutine"""
    stack_out: Sequence[str]
    """Variable names on the stack AFTER the next op executes"""
    defined_out: Sequence[str]
    """Variable names that are defined AFTER the next op executes"""
    error: str
    """Error message if failure occurs at this op"""


@attrs.frozen
class DebugInfo:
    version: int
    sources: list[str]
    mappings: str
    op_pc_offset: int
    pc_events: Mapping[int, DebugEvent]


class CompiledProgram(abc.ABC):
    @property
    @abc.abstractmethod
    def teal_src(self) -> str: ...

    @property
    @abc.abstractmethod
    def bytecode(self) -> bytes | None:
        """
        bytecode can only be produced if no template variables are used OR template values are
        provided, for this reason bytecode is only provided if output_bytecode is True
        """

    @property
    @abc.abstractmethod
    def debug_info(self) -> DebugInfo | None: ...

    @property
    @abc.abstractmethod
    def template_variables(self) -> Mapping[str, int | bytes | None]: ...

    @property
    @abc.abstractmethod
    def stats(self) -> Mapping[str, int]: ...


class CompiledContract(abc.ABC):
    @property
    @abc.abstractmethod
    def source_location(self) -> SourceLocation | None: ...

    @property
    @abc.abstractmethod
    def approval_program(self) -> CompiledProgram: ...

    @property
    @abc.abstractmethod
    def clear_program(self) -> CompiledProgram: ...

    @property
    @abc.abstractmethod
    def metadata(self) -> ContractMetaData: ...

    @typing.final
    @property
    def id(self) -> ContractReference:
        return self.metadata.ref


class CompiledLogicSig(abc.ABC):
    @property
    @abc.abstractmethod
    def source_location(self) -> SourceLocation | None: ...
    @property
    @abc.abstractmethod
    def program(self) -> CompiledProgram: ...

    @property
    @abc.abstractmethod
    def metadata(self) -> LogicSignatureMetaData: ...

    @typing.final
    @property
    def id(self) -> LogicSigReference:
        return self.metadata.ref


CompilationArtifact: typing.TypeAlias = CompiledContract | CompiledLogicSig
