import typing
import typing as t

from algopy import _primitives as stack
from algopy._contract import Contract

_P = t.ParamSpec("_P")

_R = t.TypeVar("_R")

OnCompleteActionName: t.TypeAlias = t.Literal[
    "no_op",
    "opt_in",
    "close_out",
    # "clear_state",
    "update_application",
    "delete_application",
]

# if we use type aliasing here for Callable[_P, _R], mypy thinks it involves Any... wtf
@t.overload
def abimethod(fn: t.Callable[_P, _R], /) -> t.Callable[_P, _R]: ...
@t.overload
def abimethod(
    *,
    allow_actions: t.Sequence[OnCompleteActionName] | None = None,
    # todo: use typing to exclude allow_create and
    #  require_create being specified together
    create: bool | t.Literal["allow"] = False,
    name: str | None = None,
    read_only: bool = False,
) -> t.Callable[[t.Callable[_P, _R]], t.Callable[_P, _R],]: ...

_T = t.TypeVar("_T")

class ABIEncoded(t.Protocol[_T]):
    def decode(self) -> _T:
        """Encode this ABI instance to wire format"""
    @classmethod
    def encode(cls, value: _T) -> t.Self:
        """ "Decode wire format into an ABI instance"""
    @property
    def bytes(self) -> stack.Bytes:
        """Get the underlying bytes[]"""
    @classmethod
    def from_bytes(cls, value: stack.Bytes) -> t.Self:
        """Construct an instance from the underlying bytes[] (no validation)"""

class String(ABIEncoded[stack.Bytes]):
    def __init__(self, value: stack.Bytes | t.LiteralString) -> None: ...

_TBitSize = typing.TypeVar("_TBitSize", bound=int)

class UIntN(typing.Generic[_TBitSize], ABIEncoded[stack.UInt64]):
    def __init__(self, value: stack.UInt64 | int) -> None: ...

UInt8: typing.TypeAlias = UIntN[typing.Literal[8]]
UInt16: typing.TypeAlias = UIntN[typing.Literal[16]]
UInt32: typing.TypeAlias = UIntN[typing.Literal[32]]
UInt64: typing.TypeAlias = UIntN[typing.Literal[64]]

class Bool(ABIEncoded[bool]):
    def __init__(self, value: bool) -> None: ...

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class StaticArray(typing.Generic[_TArrayItem, _TArrayLength]):
    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> t.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""
    @property
    def length(self) -> stack.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: stack.UInt64 | int | slice) -> _TArrayItem: ...

class DynamicArray(typing.Generic[_TArrayItem]):
    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> t.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""
    @property
    def length(self) -> stack.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: stack.UInt64 | int | slice) -> _TArrayItem: ...

class ARC4Contract(Contract):
    @t.final
    def approval_program(self) -> stack.UInt64 | bool: ...
    def clear_state_program(self) -> stack.UInt64 | bool: ...

class Account:
    @property
    def address(self) -> stack.Address: ...

class Asset:
    @property
    def asset_id(self) -> stack.UInt64: ...

def arc4_signature(method_signature: t.LiteralString) -> stack.Bytes: ...

class PaymentTransaction:
    @property
    def receiver(self) -> stack.Address: ...
    @property
    def amount(self) -> stack.UInt64: ...

class AssetTransferTransaction:
    @property
    def sender(self) -> stack.Address: ...
    @property
    def asset_receiver(self) -> stack.Address: ...
    @property
    def xfer_asset(self) -> stack.UInt64: ...
    @property
    def asset_amount(self) -> stack.UInt64: ...
