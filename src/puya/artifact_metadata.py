import re
import typing
from collections.abc import Sequence

import attrs
from immutabledict import immutabledict

from puya import avm
from puya.avm import AVMType
from puya.awst import nodes as awst_nodes
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference


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
        return re.split(r"\W", self.fullname)[-1]


@attrs.frozen(kw_only=True)
class MethodArgDefaultConstant:
    data: bytes
    type_: str


@attrs.frozen(kw_only=True)
class MethodArgDefaultFromState:
    kind: awst_nodes.AppStorageKind
    key: bytes
    key_type: str


@attrs.frozen(kw_only=True)
class MethodArgDefaultFromMethod:
    name: str
    return_type: str
    readonly: bool

    @property
    def signature(self) -> str:
        return f"{self.name}(){self.return_type}"


MethodArgDefault = (
    MethodArgDefaultConstant | MethodArgDefaultFromState | MethodArgDefaultFromMethod
)


@attrs.frozen
class ARC4MethodArg:
    name: str
    type_: str
    struct: str | None
    desc: str | None = attrs.field(hash=False)
    client_default: MethodArgDefault | None


@attrs.frozen
class ARC4Returns:
    type_: str
    struct: str | None
    desc: str | None = attrs.field(hash=False)


@attrs.frozen(kw_only=True)
class ARC4ABIMethod:
    id: str
    desc: str | None = attrs.field(hash=False)
    args: Sequence[ARC4MethodArg] = attrs.field(converter=tuple[ARC4MethodArg, ...])
    returns: ARC4Returns
    events: Sequence[ARC4Struct] = attrs.field(converter=tuple[ARC4Struct, ...])
    _config: awst_nodes.ARC4ABIMethodConfig

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def allowed_completion_types(self) -> Sequence[avm.OnCompletionAction]:
        return self._config.allowed_completion_types

    @property
    def create(self) -> awst_nodes.ARC4CreateOption:
        return self._config.create

    @property
    def readonly(self) -> bool:
        return self._config.readonly

    @property
    def config_location(self) -> SourceLocation:
        return self._config.source_location

    @property
    def signature(self) -> str:
        return f"{self.name}({','.join(a.type_ for a in self.args)}){self.returns.type_}"


@attrs.frozen(kw_only=True)
class ARC4BareMethod:
    id: str
    desc: str | None = attrs.field(hash=False)
    _config: awst_nodes.ARC4BareMethodConfig

    @property
    def allowed_completion_types(self) -> Sequence[avm.OnCompletionAction]:
        return self._config.allowed_completion_types

    @property
    def create(self) -> awst_nodes.ARC4CreateOption:
        return self._config.create

    @property
    def config_location(self) -> SourceLocation:
        return self._config.source_location


ARC4Method = ARC4BareMethod | ARC4ABIMethod


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
