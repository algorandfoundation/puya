import typing
from collections.abc import Callable, Mapping, Sequence

import puyapy

_P = typing.ParamSpec("_P")

_R = typing.TypeVar("_R")

AllowedOnCompletes: typing.TypeAlias = Sequence[
    typing.Literal[
        "NoOp",
        "OptIn",
        "CloseOut",
        # ClearState has its own program, so is not considered as part of ARC4 routing
        "UpdateApplication",
        "DeleteApplication",
    ]
]

# TODO: better typing for ABI methods that can be used as an argument source
# TODO: support declaring state at the class level so it can be used as a default arg source
_TABIDefaultArgSource: typing.TypeAlias = object

# if we use type aliasing here for Callable[_P, _R], mypy thinks it involves Any...
@typing.overload
def abimethod(fn: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def abimethod(
    *,
    allow_actions: AllowedOnCompletes | None = None,
    create: bool | typing.Literal["allow"] = False,
    name: str | None = None,
    readonly: bool = False,
    default_args: Mapping[str, str | _TABIDefaultArgSource] | None = None,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R],]: ...
@typing.overload
def baremethod(fn: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def baremethod(
    *,
    allow_actions: AllowedOnCompletes | None = None,
    create: bool | typing.Literal["allow"] = False,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R],]: ...

_T = typing.TypeVar("_T")

class _ABIBytesBacked(typing.Protocol):
    @property
    def bytes(self) -> puyapy.Bytes:
        """Get the underlying bytes[]"""
    @classmethod
    def from_bytes(cls, value: puyapy.Bytes) -> typing.Self:
        """Construct an instance from the underlying bytes[] (no validation)"""

class ABIEncoded(_ABIBytesBacked, typing.Protocol[_T]):
    def decode(self) -> _T:
        """Decode this ABI instance from bytes to AVM stack value"""
    @classmethod
    def encode(cls, value: _T) -> typing.Self:
        """Encode AVM stack value as an ABI bytes"""

class String(ABIEncoded[puyapy.Bytes]):
    def __init__(self, value: typing.LiteralString) -> None: ...

_TBitSize = typing.TypeVar("_TBitSize", bound=int)

class UIntN(typing.Generic[_TBitSize], ABIEncoded[puyapy.UInt64]):
    def __init__(self, value: int | puyapy.UInt64 | puyapy.BigUInt) -> None: ...

class BigUIntN(typing.Generic[_TBitSize], ABIEncoded[puyapy.BigUInt]):
    def __init__(self, value: int | puyapy.UInt64 | puyapy.BigUInt) -> None: ...

_TDecimalPlaces = typing.TypeVar("_TDecimalPlaces", bound=int)

class UFixedNxM(typing.Generic[_TBitSize, _TDecimalPlaces], ABIEncoded[puyapy.UInt64]):
    def __init__(self, value: typing.LiteralString):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """

class BigUFixedNxM(typing.Generic[_TBitSize, _TDecimalPlaces], ABIEncoded[puyapy.BigUInt]):
    def __init__(self, value: typing.LiteralString):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """

class Byte(UIntN[typing.Literal[8]]): ...

UInt8: typing.TypeAlias = UIntN[typing.Literal[8]]
UInt16: typing.TypeAlias = UIntN[typing.Literal[16]]
UInt32: typing.TypeAlias = UIntN[typing.Literal[32]]
UInt64: typing.TypeAlias = UIntN[typing.Literal[64]]
UInt128: typing.TypeAlias = BigUIntN[typing.Literal[128]]
UInt256: typing.TypeAlias = BigUIntN[typing.Literal[256]]
UInt512: typing.TypeAlias = BigUIntN[typing.Literal[512]]

class Bool(ABIEncoded[bool]):
    def __init__(self, value: bool) -> None: ...

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class StaticArray(_ABIBytesBacked, typing.Generic[_TArrayItem, _TArrayLength]):
    @typing.overload
    def __init__(self: StaticArray[_TArrayItem, typing.Literal[1]], item0: _TArrayItem): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[2]], item0: _TArrayItem, item1: _TArrayItem
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[3]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[4]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[5]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[6]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        item5: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[7]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        item5: _TArrayItem,
        item6: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[8]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        item5: _TArrayItem,
        item6: _TArrayItem,
        item7: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[9]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        item5: _TArrayItem,
        item6: _TArrayItem,
        item7: _TArrayItem,
        item8: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[10]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        item5: _TArrayItem,
        item6: _TArrayItem,
        item7: _TArrayItem,
        item8: _TArrayItem,
        item9: _TArrayItem,
    ): ...
    @typing.overload
    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""
    @property
    def length(self) -> puyapy.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: puyapy.UInt64 | int | slice) -> _TArrayItem: ...

class DynamicArray(_ABIBytesBacked, typing.Generic[_TArrayItem]):
    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""
    @property
    def length(self) -> puyapy.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: puyapy.UInt64 | int | slice) -> _TArrayItem: ...

class Address(StaticArray[Byte, typing.Literal[32]]): ...

DynamicBytes: typing.TypeAlias = DynamicArray[Byte]

class ARC4Contract(puyapy.Contract):
    @typing.final
    def approval_program(self) -> puyapy.UInt64 | bool: ...
    def clear_state_program(self) -> puyapy.UInt64 | bool: ...

_TTuple = typing.TypeVarTuple("_TTuple")

class Tuple(typing.Generic[*_TTuple], ABIEncoded[tuple[*_TTuple]], tuple[*_TTuple]):
    def __init__(self, items: tuple[*_TTuple]): ...

T = typing.TypeVar("T")

@typing.dataclass_transform(
    eq_default=False, order_default=False, kw_only_default=False, field_specifiers=()
)
class _StructMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        *,
        kw_only: bool = False,
        # **kwargs: t.Any,
    ) -> _StructMeta: ...

class Struct(metaclass=_StructMeta):
    """Base class for ARC4 Struct types"""

    @property
    def bytes(self) -> puyapy.Bytes:
        """Get the underlying bytes[]"""
    @classmethod
    def from_bytes(cls, value: puyapy.Bytes) -> typing.Self:
        """Construct an instance from the underlying bytes[] (no validation)"""
