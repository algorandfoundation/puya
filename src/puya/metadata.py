import enum
from typing import Literal, Sequence

import attrs

from puya.avm_type import AVMType
from puya.parse import SourceLocation


class OnCompletionAction(enum.IntEnum):
    NoOp = 0
    OptIn = 1
    CloseOut = 2
    ClearState = 3
    UpdateApplication = 4
    DeleteApplication = 5


@attrs.frozen(kw_only=True)
class ARC4DefaultArgument:
    parameter: str
    source: str


@attrs.frozen(kw_only=True)
class ARC4MethodConfig:
    source_location: SourceLocation
    name: str
    is_bare: bool = attrs.field(default=False)
    allow_create: bool = attrs.field(default=False)
    require_create: bool = attrs.field(default=False)
    readonly: bool = attrs.field(default=False)
    allowed_completion_types: Sequence[OnCompletionAction] = attrs.field(
        default=(OnCompletionAction.NoOp,),
        converter=tuple[OnCompletionAction],
        validator=attrs.validators.min_len(1),
    )
    default_args: Sequence[ARC4DefaultArgument] = attrs.field(
        factory=list, converter=tuple[ARC4DefaultArgument, ...]
    )
    structs: Sequence[tuple[str, "ARC32StructDef"]] = attrs.field(
        factory=list, converter=tuple[tuple[str, "ARC32StructDef"], ...]
    )
    # TODO: the rest


@attrs.define
class ARC4MethodArg:
    name: str
    type_: str
    desc: str | None


@attrs.define
class ARC4Returns:
    type_: str
    desc: str | None


@attrs.define
class ARC4Method:
    name: str
    desc: str | None
    args: list[ARC4MethodArg]
    returns: ARC4Returns
    config: ARC4MethodConfig


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
    storage_type: Literal[AVMType.uint64, AVMType.bytes]
    description: str | None


@attrs.frozen
class ContractMetaData:
    description: str | None
    name_override: str | None
    module_name: str
    class_name: str
    global_state: Sequence[ContractState]
    local_state: Sequence[ContractState]
    is_arc4: bool
    methods: Sequence[ARC4Method]

    @property
    def name(self) -> str:
        return self.name_override or self.class_name

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.class_name))
