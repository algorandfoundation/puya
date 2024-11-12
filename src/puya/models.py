import abc
import enum
import typing
from collections.abc import Mapping, Sequence

import attrs
from immutabledict import immutabledict

from puya.avm_type import AVMType
from puya.parse import SourceLocation

TemplateValue = tuple[int | bytes, SourceLocation | None]


class ContractReference(str):  # can't use typing.NewType with pattern matching
    __slots__ = ()


class LogicSigReference(str):  # can't use typing.NewType with pattern matching
    __slots__ = ()


# values and names are matched to AVM definitions
class OnCompletionAction(enum.IntEnum):
    NoOp = 0
    OptIn = 1
    CloseOut = 2
    ClearState = 3
    UpdateApplication = 4
    DeleteApplication = 5


class TransactionType(enum.IntEnum):
    pay = 1
    keyreg = 2
    acfg = 3
    axfer = 4
    afrz = 5
    appl = 6


class ARC4CreateOption(enum.Enum):
    allow = enum.auto()
    require = enum.auto()
    disallow = enum.auto()


@attrs.frozen
class ARC4StructField:
    name: str
    type: str
    struct: str | None


@attrs.frozen(kw_only=True)
class ARC4Struct:
    fullname: str
    desc: str | None = None
    fields: Sequence[ARC4StructField] = attrs.field(
        default=(), converter=tuple[ARC4StructField, ...]
    )

    @property
    def name(self) -> str:
        return self.fullname.rsplit(".", maxsplit=1)[-1]


@attrs.frozen(kw_only=True)
class ARC4BareMethodConfig:
    source_location: SourceLocation
    allowed_completion_types: Sequence[OnCompletionAction] = attrs.field(
        default=(OnCompletionAction.NoOp,),
        converter=tuple[OnCompletionAction, ...],
        validator=attrs.validators.min_len(1),
    )
    create: ARC4CreateOption = ARC4CreateOption.disallow


@attrs.frozen(kw_only=True)
class ARC4ABIMethodConfig:
    source_location: SourceLocation
    allowed_completion_types: Sequence[OnCompletionAction] = attrs.field(
        default=(OnCompletionAction.NoOp,),
        converter=tuple[OnCompletionAction],
        validator=attrs.validators.min_len(1),
    )
    create: ARC4CreateOption = ARC4CreateOption.disallow
    name: str
    readonly: bool = False
    default_args: immutabledict[str, str] = immutabledict()
    """Mapping is from parameter -> source"""


@attrs.frozen
class ARC4MethodArg:
    name: str
    type_: str
    struct: str | None
    desc: str | None = attrs.field(hash=False)


@attrs.frozen
class ARC4Returns:
    type_: str
    struct: str | None
    desc: str | None = attrs.field(hash=False)


@attrs.frozen
class ARC4ABIMethod:
    name: str
    desc: str | None = attrs.field(hash=False)
    args: Sequence[ARC4MethodArg] = attrs.field(converter=tuple[ARC4MethodArg, ...])
    returns: ARC4Returns
    events: Sequence[ARC4Struct]
    config: ARC4ABIMethodConfig

    @property
    def signature(self) -> str:
        return f"{self.name}({','.join(a.type_ for a in self.args)}){self.returns.type_}"


@attrs.frozen
class ARC4BareMethod:
    desc: str | None = attrs.field(hash=False)
    config: ARC4BareMethodConfig


@attrs.define(eq=False)
class ContractState:
    name: str
    source_location: SourceLocation
    key_or_prefix: bytes
    """Key value as bytes, or prefix if it is a map"""
    arc56_key_type: str
    arc56_value_type: str
    storage_type: typing.Literal[AVMType.uint64, AVMType.bytes]
    description: str | None
    is_map: bool
    """State describes a map"""


@attrs.frozen(kw_only=True)
class LogicSignatureMetaData:
    ref: LogicSigReference
    name: str
    description: str | None


@attrs.frozen
class StateTotals:
    global_uints: int
    local_uints: int
    global_bytes: int
    local_bytes: int


ARC4MethodConfig = ARC4BareMethodConfig | ARC4ABIMethodConfig
ARC4Method = ARC4BareMethod | ARC4ABIMethod


@attrs.frozen(kw_only=True)
class ContractMetaData:
    ref: ContractReference
    name: str
    description: str | None
    global_state: immutabledict[str, ContractState]
    local_state: immutabledict[str, ContractState]
    boxes: immutabledict[str, ContractState]
    state_totals: StateTotals
    arc4_methods: Sequence[ARC4Method]
    structs: immutabledict[str, ARC4Struct]
    template_variable_types: immutabledict[str, str]
    """Mapping of template variable names to their ARC-56 type"""

    @property
    def is_arc4(self) -> bool:
        return bool(self.arc4_methods)  # TODO: should this be an explicit flag instead?


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
