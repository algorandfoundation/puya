import typing
from collections.abc import Callable, Iterable, Mapping, Reversible, Sequence

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
    | puyapy.OnCompleteAction
]
"""Allowed completion types for ABI methods: 
NoOp, OptIn, CloseOut, UpdateApplication and DeleteApplication"""

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
) -> Callable[[Callable[_P, _R]], Callable[_P, _R],]:
    """Decorator that indicates a method is an ARC4 ABI method"""

@typing.overload
def baremethod(fn: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def baremethod(
    *,
    allow_actions: AllowedOnCompletes | None = None,
    create: bool | typing.Literal["allow"] = False,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R],]:
    """Decorator that indicates a method is an ARC4 bare method"""

_T = typing.TypeVar("_T")

def arc4_signature(signature: typing.LiteralString) -> puyapy.Bytes:
    """Returns the ARC4 encoded method selector for the specified signature"""

class _ABIEncoded(puyapy.BytesBacked, typing.Protocol[_T]):
    def decode(self) -> _T:
        """Decode this ABI instance from bytes to AVM stack value"""
    @classmethod
    def encode(cls, value: _T) -> typing.Self:
        """Encode AVM stack value as an ABI bytes"""
    @classmethod
    def from_log(cls, log: puyapy.Bytes) -> typing.Self:
        """Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`"""

class String(_ABIEncoded[puyapy.Bytes]):
    """An ARC4 sequence of bytes containing a UTF8 string"""

    def __init__(self, value: str | puyapy.Bytes) -> None: ...
    def __add__(self, other: String | str) -> String: ...
    def __iadd__(self, other: String | str) -> String: ...
    def __radd__(self, other: String | str) -> String: ...
    def __eq__(self, other: String | str) -> bool: ...  # type: ignore[override]
    def __bool__(self) -> bool:
        """Returns `True` if length is not zero"""

_TBitSize = typing.TypeVar("_TBitSize", bound=int)
_TBitSizeOther = typing.TypeVar("_TBitSizeOther", bound=int)

class UIntN(typing.Generic[_TBitSize], _ABIEncoded[puyapy.UInt64]):
    """An ARC4 UInt consisting of the number of bits specified.

    Max Size: 64 bits"""

    def __init__(self, value: int | puyapy.UInt64 | puyapy.BigUInt) -> None: ...

    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
    def __eq__(self, other: UIntN[_TBitSizeOther] | BigUIntN[_TBitSizeOther] | puyapy.UInt64 | puyapy.BigUInt | int) -> bool:  # type: ignore[override]
        ...
    def __ne__(self, other: UIntN[_TBitSizeOther] | BigUIntN[_TBitSizeOther] | puyapy.UInt64 | puyapy.BigUInt | int) -> bool:  # type: ignore[override]
        ...
    def __le__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __lt__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __ge__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __gt__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

class BigUIntN(typing.Generic[_TBitSize], _ABIEncoded[puyapy.BigUInt]):
    """An ARC4 UInt consisting of the number of bits specified.

    Max size: 512 bits"""

    def __init__(self, value: int | puyapy.UInt64 | puyapy.BigUInt) -> None: ...

    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
    def __eq__(self, other: UIntN[_TBitSizeOther] | BigUIntN[_TBitSizeOther] | puyapy.UInt64 | puyapy.BigUInt | int) -> bool:  # type: ignore[override]
        ...
    def __ne__(self, other: UIntN[_TBitSizeOther] | BigUIntN[_TBitSizeOther] | puyapy.UInt64 | puyapy.BigUInt | int) -> bool:  # type: ignore[override]
        ...
    def __le__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __lt__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __ge__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __gt__(
        self,
        other: UIntN[_TBitSizeOther]
        | BigUIntN[_TBitSizeOther]
        | puyapy.UInt64
        | puyapy.BigUInt
        | int,
    ) -> bool: ...
    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

_TDecimalPlaces = typing.TypeVar("_TDecimalPlaces", bound=int)

class UFixedNxM(typing.Generic[_TBitSize, _TDecimalPlaces], _ABIEncoded[puyapy.UInt64]):
    """An ARC4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 64 bits"""

    def __init__(self, value: typing.LiteralString):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """
    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

class BigUFixedNxM(typing.Generic[_TBitSize, _TDecimalPlaces], _ABIEncoded[puyapy.BigUInt]):
    """An ARC4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 512 bits"""

    def __init__(self, value: typing.LiteralString):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """
    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

class Byte(UIntN[typing.Literal[8]]):
    """An ARC4 alias for a UInt8"""

UInt8: typing.TypeAlias = UIntN[typing.Literal[8]]
"""An ARC4 UInt8"""

UInt16: typing.TypeAlias = UIntN[typing.Literal[16]]
"""An ARC4 UInt16"""

UInt32: typing.TypeAlias = UIntN[typing.Literal[32]]
"""An ARC4 UInt32"""

UInt64: typing.TypeAlias = UIntN[typing.Literal[64]]
"""An ARC4 UInt64"""

UInt128: typing.TypeAlias = BigUIntN[typing.Literal[128]]
"""An ARC4 UInt128"""

UInt256: typing.TypeAlias = BigUIntN[typing.Literal[256]]
"""An ARC4 UInt256"""

UInt512: typing.TypeAlias = BigUIntN[typing.Literal[512]]
"""An ARC4 UInt512"""

class Bool(_ABIEncoded[bool]):
    """An ARC4 encoded bool"""

    def __init__(self, value: bool) -> None: ...  # noqa: FBT001

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class StaticArray(
    puyapy.BytesBacked,
    typing.Generic[_TArrayItem, _TArrayLength],
    Reversible[_TArrayItem],
):
    """A fixed length ARC4 Array of the specified type and length"""

    @typing.overload
    def __init__(self) -> None: ...
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
    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""
    @property
    def length(self) -> puyapy.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: puyapy.UInt64 | int | slice) -> _TArrayItem: ...
    def __setitem__(self, index: puyapy.UInt64 | int, value: _TArrayItem) -> _TArrayItem: ...
    def copy(self) -> typing.Self:
        """Create a copy of this array"""

class DynamicArray(puyapy.BytesBacked, typing.Generic[_TArrayItem], Reversible[_TArrayItem]):
    """A dynamically sized ARC4 Array of the specified type"""

    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""
    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""
    @property
    def length(self) -> puyapy.UInt64:
        """Returns the current length of the array"""
    def __getitem__(self, index: puyapy.UInt64 | int | slice) -> _TArrayItem: ...
    def append(self, item: _TArrayItem) -> None:
        """Append items to this array"""
    def extend(self, other: Iterable[_TArrayItem]) -> None:
        """Extend this array with the contents of another array"""
    def __setitem__(self, index: puyapy.UInt64 | int, value: _TArrayItem) -> _TArrayItem: ...
    def __add__(self, other: Iterable[_TArrayItem]) -> DynamicArray[_TArrayItem]: ...
    def pop(self) -> _TArrayItem: ...
    def copy(self) -> typing.Self:
        """Create a copy of this array"""
    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

class Address(StaticArray[Byte, typing.Literal[32]]):
    """An alias for an array containing 32 bytes representing an Algorand address"""

    def __init__(self, account_or_bytes: puyapy.Bytes | puyapy.Account | bytes): ...
    def __bool__(self) -> bool:
        """Returns `True` if not equal to the zero address"""

class DynamicBytes(_ABIEncoded[puyapy.Bytes], DynamicArray[Byte]):
    """A variable sized array of bytes"""

    @typing.overload
    def __init__(self, *values: Byte | UInt8 | int): ...
    @typing.overload
    def __init__(self, value: puyapy.Bytes | bytes, /): ...

class ARC4Contract(puyapy.Contract):
    """A contract that conforms to the ARC4 ABI specification, functions decorated with
    `@abimethod` or `@baremethod` will form the public interface of the contract

    The approval_program will be implemented by the compiler, and route application args
    according to the ARC4 ABI specification

    The clear_state_program will by default return True, but can be overridden"""

    @typing.final
    def approval_program(self) -> puyapy.UInt64 | bool: ...
    def clear_state_program(self) -> puyapy.UInt64 | bool: ...

_TTuple = typing.TypeVarTuple("_TTuple")

class Tuple(
    typing.Generic[typing.Unpack[_TTuple]],
    _ABIEncoded[tuple[typing.Unpack[_TTuple]]],
    tuple[typing.Unpack[_TTuple]],
):
    """An ARC4 ABI tuple, containing other ARC4 ABI types"""

    def __init__(self, items: tuple[typing.Unpack[_TTuple]]): ...

@typing.dataclass_transform(
    eq_default=False, order_default=False, kw_only_default=False, field_specifiers=()
)
class _StructMeta(type):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        *,
        kw_only: bool = False,
        # **kwargs: typing.Any,
    ) -> _StructMeta: ...

class Struct(metaclass=_StructMeta):
    """Base class for ARC4 Struct types"""

    @property
    def bytes(self) -> puyapy.Bytes:
        """Get the underlying bytes[]"""
    @classmethod
    def from_bytes(cls, value: puyapy.Bytes) -> typing.Self:
        """Construct an instance from the underlying bytes[] (no validation)"""
    def copy(self) -> typing.Self:
        """Create a copy of this struct"""

class ARC4Client(typing.Protocol): ...

_TABIResult_co = typing.TypeVar("_TABIResult_co", covariant=True)
_TABIArg = (
    puyapy.BytesBacked
    | puyapy.UInt64
    | puyapy.Bytes
    | puyapy.Asset
    | puyapy.Account
    | puyapy.Application
    | int
    | bool
    | bytes
    | str
)

class _ABICallWithReturnProtocol(typing.Protocol[_TABIResult_co]):
    def __call__(
        self,
        method: str,
        /,
        *args: _TABIArg,
        app_id: puyapy.Application | puyapy.UInt64 | int = ...,
        on_completion: puyapy.OnCompleteAction = ...,
        approval_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        clear_state_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        fee: puyapy.UInt64 | int = ...,
        sender: puyapy.Account | str = ...,
        note: puyapy.Bytes | bytes = ...,
        rekey_to: puyapy.Account | str = ...,
    ) -> tuple[_TABIResult_co, puyapy.itxn.ApplicationCallInnerTransaction]: ...

class _ABICallProtocolType(typing.Protocol):
    @typing.overload
    def __call__(  # type: ignore[misc]
        self,
        method: Callable[..., None] | str,
        /,
        *args: _TABIArg,
        app_id: puyapy.Application | puyapy.UInt64 | int = ...,
        on_completion: puyapy.OnCompleteAction = ...,
        approval_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        clear_state_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        fee: puyapy.UInt64 | int = ...,
        sender: puyapy.Account | str = ...,
        note: puyapy.Bytes | bytes = ...,
        rekey_to: puyapy.Account | str = ...,
    ) -> puyapy.itxn.ApplicationCallInnerTransaction: ...
    @typing.overload
    def __call__(  # type: ignore[misc]
        self,
        method: Callable[..., _TABIResult_co],
        /,
        *args: _TABIArg,
        app_id: puyapy.Application | puyapy.UInt64 | int = ...,
        on_completion: puyapy.OnCompleteAction = ...,
        approval_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        clear_state_program: puyapy.Bytes | bytes | tuple[puyapy.Bytes, ...] = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        fee: puyapy.UInt64 | int = ...,
        sender: puyapy.Account | str = ...,
        note: puyapy.Bytes | bytes = ...,
        rekey_to: puyapy.Account | str = ...,
    ) -> tuple[_TABIResult_co, puyapy.itxn.ApplicationCallInnerTransaction]: ...
    def __getitem__(
        self, _: type[_TABIResult_co]
    ) -> _ABICallWithReturnProtocol[_TABIResult_co]: ...

abi_call: _ABICallProtocolType = ...
"""Provides a typesafe way of calling ARC4 methods via an inner transaction

Examples:
```
# can reference another puyapy contract method
result, txn = abi_call(HelloWorldContract.hello, arc4.String("World"), app=...)
assert result == "Hello, World"

# can reference a method selector
result, txn = abi_call[arc4.String]("hello(string)string", arc4.String("Algo"), app=...)
assert result == "Hello, Algo"

# can reference a method name, the method selector is inferred from arguments and return type
result, txn = abi_call[arc4.String]("hello", "There", app=...)
assert result == "Hello, There"
```


"""
