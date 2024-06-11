from __future__ import annotations

import enum
import typing

import attrs
from immutabledict import immutabledict

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from puya.avm_type import AVMType
    from puya.parse import SourceLocation
    from puya.teal.models import TealProgram


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


@attrs.frozen(kw_only=True)
class ARC4BareMethodConfig:
    source_location: SourceLocation | None
    allowed_completion_types: Sequence[OnCompletionAction] = attrs.field(
        default=(OnCompletionAction.NoOp,),
        converter=tuple[OnCompletionAction],
        validator=attrs.validators.min_len(1),
    )
    create: ARC4CreateOption = ARC4CreateOption.disallow


@attrs.frozen(kw_only=True)
class ARC4ABIMethodConfig:
    source_location: SourceLocation | None
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
    structs: immutabledict[str, ARC32StructDef] = immutabledict()


@attrs.frozen
class ARC4MethodArg:
    name: str
    type_: str
    desc: str | None = attrs.field(hash=False)


@attrs.frozen
class ARC4Returns:
    type_: str
    desc: str | None = attrs.field(hash=False)


@attrs.frozen
class ARC4ABIMethod:
    name: str
    desc: str | None = attrs.field(hash=False)
    args: Sequence[ARC4MethodArg] = attrs.field(converter=tuple[ARC4MethodArg, ...])
    returns: ARC4Returns
    config: ARC4ABIMethodConfig


@attrs.frozen
class ARC4BareMethod:
    desc: str | None = attrs.field(hash=False)
    config: ARC4BareMethodConfig


@attrs.frozen
class ARC32StructDef:
    name: str
    elements: Sequence[tuple[str, str]] = attrs.field(
        factory=list, converter=tuple[tuple[str, str], ...]
    )


@attrs.define(eq=False)
class ContractState:
    name: str
    source_location: SourceLocation
    key: bytes
    storage_type: typing.Literal[AVMType.uint64, AVMType.bytes]
    description: str | None


@attrs.frozen
class LogicSignatureMetaData:
    module_name: str
    name: str
    description: str | None

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.name))


@attrs.frozen
class StateTotals:
    global_uints: int
    local_uints: int
    global_bytes: int
    local_bytes: int


ARC4MethodConfig = ARC4BareMethodConfig | ARC4ABIMethodConfig
ARC4Method = ARC4BareMethod | ARC4ABIMethod


@attrs.frozen
class ContractMetaData:
    description: str | None
    name_override: str | None
    module_name: str
    class_name: str
    global_state: immutabledict[str, ContractState]
    local_state: immutabledict[str, ContractState]
    state_totals: StateTotals
    arc4_methods: Sequence[ARC4Method]

    @property
    def is_arc4(self) -> bool:
        return bool(self.arc4_methods)

    @property
    def name(self) -> str:
        return self.name_override or self.class_name

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.class_name))


TemplateVariables = tuple[tuple[str, int | bytes], ...]


@attrs.frozen(kw_only=True)
class CompiledProgram:
    teal: TealProgram
    teal_src: str
    bytecodes: Mapping[TemplateVariables, bytes]

    @property
    def bytecode(self) -> bytes:
        """Returns the bytecode for the program using CLI template values"""
        return self.get_bytecode_overrides(None)

    def get_bytecode_overrides(
        self, template_variables: Mapping[str, int | bytes] | None
    ) -> bytes:
        """Returns bytecode for the program when using the specified template overrides"""
        template_variables = template_variables or {}
        key = tuple(sorted((k, v) for k, v in template_variables.items()))
        return self.bytecodes[key]


@attrs.frozen(kw_only=True)
class CompiledContract:
    approval_program: CompiledProgram
    clear_program: CompiledProgram
    metadata: ContractMetaData


@attrs.frozen(kw_only=True)
class CompiledLogicSignature:
    program: CompiledProgram
    metadata: LogicSignatureMetaData


CompilationArtifact: typing.TypeAlias = CompiledContract | CompiledLogicSignature


class CompiledReferenceField(enum.StrEnum):
    approval = enum.auto()
    clear_state = enum.auto()
    account = enum.auto()  # logic sig only
    global_uints = enum.auto()
    global_bytes = enum.auto()
    local_uints = enum.auto()
    local_bytes = enum.auto()
    extra_program_pages = enum.auto()
