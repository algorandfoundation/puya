# ruff: noqa: N815
import enum
import typing
from collections.abc import Mapping, Sequence

import attrs

ABIType = str
"""An ABI-encoded type"""
StructName = str
"""The name of a defined struct"""
ProgramType = typing.Literal["approval", "clear"]


class AVMType(enum.StrEnum):
    """A native AVM type"""

    bytes = "AVMBytes"
    """Raw byteslice without the length prefixed that is specified in ARC-4"""
    string = "AVMString"
    """A utf-8 string without the length prefix that is specified in ARC-4"""
    uint64 = "AVMUint64"
    """A 64-bit unsigned integer"""


@attrs.frozen
class SourceInfo:
    pc: Sequence[int]
    """The program counter value(s). Could be offset if pcOffsetMethod is not 'none'"""
    errorMessage: str
    """A human-readable string that describes the error when the program fails at the given PC"""


@attrs.frozen
class ProgramSourceInfo:
    sourceInfo: Sequence[SourceInfo]
    """The source information for the program"""
    pcOffsetMethod: typing.Literal["none", "cblocks"]
    """
    How the program counter offset is calculated
    none: The pc values in sourceInfo are not offset
    cblocks: The pc values in sourceInfo are offset by the PC of the first op after the
             last cblock at the top of the program
    """


@attrs.frozen(kw_only=True)
class StorageKey:
    """Describes a single key in app storage"""

    desc: str | None = None
    """Description of what this storage key holds"""
    keyType: ABIType | AVMType | StructName
    """The type of the key"""
    valueType: ABIType | AVMType | StructName
    """The type of the value"""
    key: str
    """The base64-encoded key"""


@attrs.frozen(kw_only=True)
class StorageMap:
    """Describes a mapping of key-value pairs in storage"""

    desc: str | None = None
    """Description of what the key-value pairs in this mapping hold"""
    keyType: ABIType | AVMType | StructName
    """The type of the keys in the map"""
    valueType: ABIType | AVMType | StructName
    """The type of the values in the map"""
    prefix: str | None = None
    """The base64-encoded prefix of the map keys"""


@attrs.frozen
class StructField:
    """Information about a single field in a struct"""

    name: str
    """The name of the struct field"""
    type: ABIType | StructName | Sequence["StructField"]
    """The type of the struct field's value"""


@attrs.frozen
class EventArg:
    type: ABIType
    """
    The type of the argument.
    The `struct` field should also be checked to determine if this arg is a struct.
    """
    name: str | None = None
    """Optional, user-friendly name for the argument"""
    desc: str | None = None
    """Optional, user-friendly description for the argument"""
    struct: StructName | None = None
    """
    If the type is a struct, the name of the struct
    Note: this is a separate field to maintain backwards compatability with ARC-23
    """


@attrs.frozen(kw_only=True)
class Event:
    name: str
    """The name of the event"""
    desc: str | None = None
    """Optional, user-friendly description for the event"""
    args: Sequence[EventArg]
    """The arguments of the event, in order"""


class DefaultValueSource(enum.Enum):
    box = "box"
    """The data key signifies the box key to read the value from"""
    global_ = "global"
    """The data key signifies the global state key to read the value from"""
    local_ = "local"
    """The data key signifies the local state key to read the value from (for the sender)"""
    literal = "literal"
    """the value is a literal and should be passed directly as the argument"""
    method = "method"
    """
    The utf8 signature of the method in this contract to call to get the default value.
    If the method has arguments, they all must have default values.
    The method **MUST** be readonly so simulate can be used to get the default value.
    """


@attrs.frozen(kw_only=True)
class MethodArgDefaultValue:
    source: DefaultValueSource
    """Where the default value is coming from"""
    type: ABIType | AVMType | None = None
    """
    How the data is encoded.
    This is the encoding for the data provided here, not the arg type.
    Not relevant if source is method
    """
    data: str
    """Base64 encoded bytes, base64 ARC-4 encoded uint64, or UTF-8 method selector"""


@attrs.frozen(kw_only=True)
class MethodArg:
    type: ABIType
    """
    The type of the argument.
    The `struct` field should also be checked to determine if this arg is a struct.
    """
    struct: StructName | None = None
    """
    If the type is a struct, the name of the struct.
    Note: this is a separate field to maintain backwards compatability with ARC-4
    """
    name: str | None = None
    """Optional, user-friendly name for the argument"""
    desc: str | None = None
    """Optional, user-friendly description for the argument"""
    defaultValue: MethodArgDefaultValue | None = None


@attrs.frozen(kw_only=True)
class MethodReturns:
    type: ABIType
    """
    The type of the return value, or "void" to indicate no return value.
    The `struct` field should also be checked to determine if this return value is a struct.
    """
    struct: StructName | None = None
    """
    If the type is a struct, the name of the struct
    """
    desc: str | None = None
    """Optional, user-friendly description for the return value"""


@attrs.frozen
class MethodActions:
    """An action is a combination of call/create and an OnComplete"""

    create: Sequence[typing.Literal["NoOp", "OptIn", "DeleteApplication"]]
    """OnCompletes this method allows when appID === 0"""
    call: Sequence[
        typing.Literal["NoOp", "OptIn", "CloseOut", "UpdateApplication", "DeleteApplication"]
    ]
    """OnCompletes this method allows when appID !== 0"""


@attrs.frozen(kw_only=True)
class MethodBoxRecommendation:
    app: int | None = None
    """The app ID for the box"""
    key: str
    """The base64 encoded box key"""
    readBytes: int
    """The number of bytes being read from the box"""
    writeBytes: int
    """The number of bytes being written to the box"""


@attrs.frozen(kw_only=True)
class MethodRecommendations:
    innerTransactionCount: int | None = None
    """The number of inner transactions the caller should cover the fees for"""
    boxes: MethodBoxRecommendation | None = None
    """Recommended box references to include"""
    accounts: Sequence[str] | None = None
    """Recommended foreign accounts"""
    apps: Sequence[int] | None = None
    """Recommended foreign apps"""
    assets: Sequence[int] | None = None
    """Recommended foreign assets"""


@attrs.frozen(kw_only=True)
class Method:
    """
    Describes a method in the contract.
    This interface is an extension of the interface described in ARC-4
    """

    name: str
    """The name of the method"""
    desc: str | None = None
    """Optional, user-friendly description for the method"""
    args: Sequence[MethodArg]
    """The arguments of the method, in order"""
    returns: MethodReturns
    """Information about the method's return value"""
    actions: MethodActions
    """Allowed actions for this method"""
    readonly: bool
    """If this method does not write anything to the ledger (ARC-22)"""
    events: Sequence[Event] = ()
    """ARC-28 events that MAY be emitted by this method"""
    recommendations: MethodRecommendations | None = None
    """Information that clients can use when calling the method"""


@attrs.frozen
class Network:
    appID: int
    """The app ID of the deployed contract in this network"""


class SchemaSizes(typing.TypedDict):
    ints: int
    bytes: int


ContractSchema = typing.TypedDict("ContractSchema", {"global": SchemaSizes, "local": SchemaSizes})
StorageMaps = Mapping[str, StorageMap]
StorageKeys = Mapping[str, StorageKey]
ContractStorage = typing.TypedDict(
    "ContractStorage", {"global": StorageMaps, "local": StorageMaps, "box": StorageMaps}
)
ContractKeys = typing.TypedDict(
    "ContractKeys", {"global": StorageKeys, "local": StorageKeys, "box": StorageKeys}
)


@attrs.frozen
class ContractState:
    schema: ContractSchema
    """
    Defines the values that should be used for GlobalNumUint, GlobalNumByteSlice, LocalNumUint,
    and LocalNumByteSlice when creating the application
    """
    keys: ContractKeys
    """Mapping of human-readable names to StorageKey objects"""
    maps: ContractStorage
    """Mapping of human-readable names to StorageMap objects"""


@attrs.frozen(kw_only=True)
class CompilerVersion:
    major: int
    minor: int
    patch: int
    commitHash: str | None = None


@attrs.frozen
class CompilerInfo:
    compiler: str
    """The name of the compiler"""
    compilerVersion: CompilerVersion


@attrs.frozen(kw_only=True)
class TemplateVariable:
    type: ABIType | AVMType | StructName
    """The type of the template variable"""
    value: str | None = None
    """If given, the the base64 encoded value used for the given app/program"""


@attrs.frozen
class ScratchVariable:
    slot: int
    type: ABIType | AVMType | StructName


@attrs.frozen(kw_only=True)
class Contract:
    """
    Describes the entire contract.
    This interface is an extension of the interface described in ARC-4
    """

    arcs: Sequence[int] = ()
    """
    The ARCs used and/or supported by this contract.
    All contracts implicitly support ARC-4 and ARC-56
    """
    name: str
    """A user-friendly name for the contract"""
    desc: str | None = None
    """Optional, user-friendly description for the interface"""
    networks: Mapping[str, Network] | None = None
    """
    Optional object listing the contract instances across different networks.
    The key is the base64 genesis hash of the network, and the value contains
    information about the deployed contract in the network indicated by the
    key. A key containing the human-readable name of the network MAY be
    included, but the corresponding genesis hash key MUST also be define
    """
    structs: Mapping[str, Sequence[StructField]]
    """
    Named structs use by the application.
    Each struct field appears in the same order as ABI encoding
    """
    methods: Sequence[Method]
    """All of the methods that the contract implements"""
    state: ContractState | None = None
    bareActions: MethodActions | None = None
    """Supported bare actions for the contract"""
    sourceInfo: Mapping[ProgramType, ProgramSourceInfo] | None = None
    """Information about the TEAL programs"""
    source: Mapping[ProgramType, str] | None = None
    """
    The pre-compiled TEAL that may contain template variables.
    MUST be omitted if included as part of ARC-23
    """
    byteCode: Mapping[ProgramType, str] | None = None
    """
    The compiled bytecode for the application.
    MUST be omitted if included as part of ARC-23
    """
    compilerInfo: CompilerInfo | None = None
    """
    Information used to get the given byteCode and/or PC values in sourceInfo.
    MUST be given if byteCode or PC values are present
    """
    events: Sequence[Event] | None = None
    """ARC-28 events that MAY be emitted by this contract"""
    templateVariables: Mapping[str, TemplateVariable] | None = None
    """
    A mapping of template variable names as they appear in the teal (not including TMPL_ prefix)
    to their respective types and values (if applicable)
    """
    scratchVariables: Mapping[str, ScratchVariable] | None = None
    """The scratch variables used during runtime"""
