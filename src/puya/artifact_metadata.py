import re
import typing
from collections.abc import Sequence

import attrs
from immutabledict import immutabledict

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
    id: str
    name: str
    desc: str | None = attrs.field(hash=False)
    args: Sequence[ARC4MethodArg] = attrs.field(converter=tuple[ARC4MethodArg, ...])
    returns: ARC4Returns
    events: Sequence[ARC4Struct]
    config: awst_nodes.ARC4ABIMethodConfig

    @property
    def signature(self) -> str:
        return f"{self.name}({','.join(a.type_ for a in self.args)}){self.returns.type_}"


@attrs.frozen
class ARC4BareMethod:
    id: str
    desc: str | None = attrs.field(hash=False)
    config: awst_nodes.ARC4BareMethodConfig


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
