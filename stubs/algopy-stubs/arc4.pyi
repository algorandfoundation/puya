import typing
from collections.abc import Callable, Iterable, Mapping, Reversible, Sequence

import algopy

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")

_ReadOnlyNoArgsMethod: typing.TypeAlias = Callable[..., typing.Any]  # type: ignore[misc]

class ARC4Contract(algopy.Contract):
    """A contract that conforms to the ARC-4 ABI specification, functions decorated with
    `@abimethod` or `@baremethod` will form the public interface of the contract

    The approval_program will be implemented by the compiler, and route application args
    according to the ARC-4 ABI specification

    The clear_state_program will by default return True, but can be overridden"""

    def approval_program(self) -> bool: ...
    def clear_state_program(self) -> algopy.UInt64 | bool: ...

# if we use type aliasing here for Callable[_P, _R], mypy thinks it involves Any...
@typing.overload
def abimethod(fn: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def abimethod(
    *,
    name: str = ...,
    create: typing.Literal["allow", "require", "disallow"] = "disallow",
    allow_actions: Sequence[
        algopy.OnCompleteAction
        | typing.Literal[
            "NoOp",
            "OptIn",
            "CloseOut",
            # ClearState has its own program, so is not considered as part of ARC-4 routing
            "UpdateApplication",
            "DeleteApplication",
        ]
    ] = ("NoOp",),
    readonly: bool = False,
    default_args: Mapping[str, str | _ReadOnlyNoArgsMethod | object] = ...,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Decorator that indicates a method is an ARC-4 ABI method.

    :arg name: Name component of the ABI method selector. Defaults to using the function name.
    :arg create: Controls the validation of the Application ID. "require" means it must be zero,
                 "disallow" requires it must be non-zero, and "allow" disables the validation.
    :arg allow_actions: A sequence of allowed On-Completion Actions to validate against.
    :arg readonly: If True, then this method can be used via dry-run / simulate.
    :arg default_args: Default argument sources for clients to use. For dynamic defaults, this can
                       be the name of, or reference to a method member, or the name of a storage
                       member. For static defaults, this can be any expression which evaluates to
                       a compile time constant of the exact same type as the parameter.

    """

_TARC4Contract = typing.TypeVar("_TARC4Contract", bound=ARC4Contract)

@typing.overload
def baremethod(fn: Callable[[_TARC4Contract], None], /) -> Callable[[_TARC4Contract], None]: ...
@typing.overload
def baremethod(
    *,
    create: typing.Literal["allow", "require", "disallow"] = "disallow",
    allow_actions: Sequence[
        algopy.OnCompleteAction
        | typing.Literal[
            "NoOp",
            "OptIn",
            "CloseOut",
            # ClearState has its own program, so is not considered as part of ARC-4 routing
            "UpdateApplication",
            "DeleteApplication",
        ]
    ] = ...,
) -> Callable[[Callable[[_TARC4Contract], None]], Callable[[_TARC4Contract], None]]:
    """Decorator that indicates a method is an ARC-4 bare method.

    There can be only one bare method on a contract for each given On-Completion Action.

    :arg create: Controls the validation of the Application ID. "require" means it must be zero,
                 "disallow" requires it must be non-zero, and "allow" disables the validation.
    :arg allow_actions: Which On-Completion Action(s) to handle.
    """

def arc4_signature(signature: str | Callable[_P, _R], /) -> algopy.Bytes:
    """Returns the ARC-4 encoded method selector for the specified signature or abi method"""

class _ABIEncoded(algopy.BytesBacked, typing.Protocol):
    @classmethod
    def from_log(cls, log: algopy.Bytes, /) -> typing.Self:
        """
        Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`
        """

class String(_ABIEncoded):
    """An ARC-4 sequence of bytes containing a UTF8 string"""

    def __init__(self, value: algopy.String | str = "", /) -> None: ...
    @property
    def native(self) -> algopy.String:
        """Return the String representation of the UTF8 string after ARC-4 decoding"""

    def __add__(self, other: String | algopy.String | str) -> String: ...
    def __iadd__(self, other: String | algopy.String | str) -> String: ...
    def __radd__(self, other: String | algopy.String | str) -> String: ...
    def __eq__(self, other: String | algopy.String | str) -> bool: ...  # type: ignore[override]
    def __bool__(self) -> bool:
        """Returns `True` if length is not zero"""

_TBitSize = typing.TypeVar("_TBitSize", bound=int)

class _UIntN(_ABIEncoded, typing.Protocol):
    def __init__(self, value: algopy.BigUInt | algopy.UInt64 | int = 0, /) -> None: ...

    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
    def __eq__(  # type: ignore[override]
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __ne__(  # type: ignore[override]
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __le__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __lt__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __ge__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __gt__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool: ...
    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

class UIntN(_UIntN, typing.Generic[_TBitSize]):
    """An ARC-4 UInt consisting of the number of bits specified.

    Max Size: 64 bits"""

    @property
    def native(self) -> algopy.UInt64:
        """Return the UInt64 representation of the value after ARC-4 decoding"""

class BigUIntN(_UIntN, typing.Generic[_TBitSize]):
    """An ARC-4 UInt consisting of the number of bits specified.

    Max size: 512 bits"""

    @property
    def native(self) -> algopy.BigUInt:
        """Return the BigUInt representation of the value after ARC-4 decoding"""

_TDecimalPlaces = typing.TypeVar("_TDecimalPlaces", bound=int)

class UFixedNxM(_ABIEncoded, typing.Generic[_TBitSize, _TDecimalPlaces]):
    """An ARC-4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 64 bits"""

    def __init__(self, value: str = "0.0", /):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """

    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

    def __eq__(self, other: typing.Self) -> bool:  # type: ignore[override]
        """Compare for equality, note both operands must be the exact same type"""

class BigUFixedNxM(_ABIEncoded, typing.Generic[_TBitSize, _TDecimalPlaces]):
    """An ARC-4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 512 bits"""

    def __init__(self, value: str = "0.0", /):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """

    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""

    def __eq__(self, other: typing.Self) -> bool:  # type: ignore[override]
        """Compare for equality, note both operands must be the exact same type"""

class Byte(UIntN[typing.Literal[8]]):
    """An ARC-4 alias for a UInt8"""

UInt8: typing.TypeAlias = UIntN[typing.Literal[8]]
"""An ARC-4 UInt8"""

UInt16: typing.TypeAlias = UIntN[typing.Literal[16]]
"""An ARC-4 UInt16"""

UInt32: typing.TypeAlias = UIntN[typing.Literal[32]]
"""An ARC-4 UInt32"""

UInt64: typing.TypeAlias = UIntN[typing.Literal[64]]
"""An ARC-4 UInt64"""

UInt128: typing.TypeAlias = BigUIntN[typing.Literal[128]]
"""An ARC-4 UInt128"""

UInt256: typing.TypeAlias = BigUIntN[typing.Literal[256]]
"""An ARC-4 UInt256"""

UInt512: typing.TypeAlias = BigUIntN[typing.Literal[512]]
"""An ARC-4 UInt512"""

class Bool(_ABIEncoded):
    """An ARC-4 encoded bool"""

    def __init__(self, value: bool = False, /) -> None: ...  # noqa: FBT001, FBT002
    def __eq__(self, other: Bool | bool) -> bool: ...  # type: ignore[override]
    def __ne__(self, other: Bool | bool) -> bool: ...  # type: ignore[override]
    @property
    def native(self) -> bool:
        """Return the bool representation of the value after ARC-4 decoding"""

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class StaticArray(
    _ABIEncoded,
    typing.Generic[_TArrayItem, _TArrayLength],
    Reversible[_TArrayItem],
):
    """A fixed length ARC-4 Array of the specified type and length"""

    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self: StaticArray[_TArrayItem, typing.Literal[1]], item0: _TArrayItem, /): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[2]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        /,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[3]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        /,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[4]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        /,
    ): ...
    @typing.overload
    def __init__(
        self: StaticArray[_TArrayItem, typing.Literal[5]],
        item0: _TArrayItem,
        item1: _TArrayItem,
        item2: _TArrayItem,
        item3: _TArrayItem,
        item4: _TArrayItem,
        /,
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
        /,
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
        /,
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
        /,
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
        /,
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
        /,
    ): ...
    @typing.overload
    def __init__(self, *items: _TArrayItem): ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at specified index to provided value"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

class DynamicArray(_ABIEncoded, typing.Generic[_TArrayItem], Reversible[_TArrayItem]):
    """A dynamically sized ARC-4 Array of the specified type"""

    def __init__(self, *items: _TArrayItem):
        """Initializes a new array with items provided"""

    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def append(self, item: _TArrayItem, /) -> None:
        """Append an item to this array"""

    def extend(self, other: Iterable[_TArrayItem], /) -> None:
        """Extend this array with the contents of another array"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at specified index to provided value"""

    def __add__(self, other: Iterable[_TArrayItem]) -> DynamicArray[_TArrayItem]:
        """Concat two arrays together, returning a new array"""

    def pop(self) -> _TArrayItem:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

class Address(StaticArray[Byte, typing.Literal[32]]):
    """An alias for an array containing 32 bytes representing an Algorand address"""

    def __init__(self, value: algopy.Account | str | algopy.Bytes = ..., /):
        """
        If `value` is a string, it should be a 58 character base32 string,
        ie a base32 string-encoded 32 bytes public key + 4 bytes checksum.
        If `value` is a Bytes, it's length checked to be 32 bytes - to avoid this
        check, use `Address.from_bytes(...)` instead.
        Defaults to the zero-address.
        """

    @property
    def native(self) -> algopy.Account:
        """Return the Account representation of the address after ARC-4 decoding"""

    def __bool__(self) -> bool:
        """Returns `True` if not equal to the zero address"""

    def __eq__(self, other: Address | algopy.Account | str) -> bool:  # type: ignore[override]
        """Address equality is determined by the address of another
        `arc4.Address`, `Account` or `str`"""

    def __ne__(self, other: Address | algopy.Account | str) -> bool:  # type: ignore[override]
        """Address equality is determined by the address of another
        `arc4.Address`, `Account` or `str`"""

class DynamicBytes(DynamicArray[Byte]):
    """A variable sized array of bytes"""

    @typing.overload
    def __init__(self, *values: Byte | UInt8 | int): ...
    @typing.overload
    def __init__(self, value: algopy.Bytes | bytes, /): ...
    @property
    def native(self) -> algopy.Bytes:
        """Return the Bytes representation of the address after ARC-4 decoding"""

_TTuple = typing.TypeVarTuple("_TTuple")

class Tuple(_ABIEncoded, tuple[typing.Unpack[_TTuple]]):
    """An ARC-4 ABI tuple, containing other ARC-4 ABI types"""

    def __init__(self, items: tuple[typing.Unpack[_TTuple]], /):
        """Construct an ARC-4 tuple from a native Python tuple"""

    @property
    def native(self) -> tuple[typing.Unpack[_TTuple]]:
        """Convert to a native Python tuple - note that the elements of the tuple
        should be considered to be copies of the original elements"""

    def copy(self) -> typing.Self:
        """Create a copy of this tuple"""

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
    ) -> _StructMeta: ...

class Struct(metaclass=_StructMeta):
    """Base class for ARC-4 Struct types"""

    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes[] (no validation)"""

    @property
    def bytes(self) -> algopy.Bytes:
        """Get the underlying bytes[]"""

    @classmethod
    def from_log(cls, log: algopy.Bytes, /) -> typing.Self:
        """Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`"""

    def copy(self) -> typing.Self:
        """Create a copy of this struct"""

    def _replace(self, **kwargs: typing.Any) -> typing.Self:  # type: ignore[misc]
        """Return a new instance of the struct replacing specified fields with new values.

        Note that any mutable fields must be explicitly copied to avoid aliasing."""

class ARC4Client(typing.Protocol):
    """Used to provide typed method signatures for ARC-4 contracts"""

_TABIResult_co = typing.TypeVar("_TABIResult_co", covariant=True)

class _ABICallWithReturnProtocol(typing.Protocol[_TABIResult_co]):
    def __call__(
        self,
        method: str,
        /,
        *args: object,
        app_id: algopy.Application | algopy.UInt64 | int = ...,
        on_completion: algopy.OnCompleteAction = ...,
        approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        global_num_uint: algopy.UInt64 | int = ...,
        global_num_bytes: algopy.UInt64 | int = ...,
        local_num_uint: algopy.UInt64 | int = ...,
        local_num_bytes: algopy.UInt64 | int = ...,
        extra_program_pages: algopy.UInt64 | int = ...,
        fee: algopy.UInt64 | int = 0,
        sender: algopy.Account | str = ...,
        note: algopy.Bytes | bytes | str = ...,
        rekey_to: algopy.Account | str = ...,
    ) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]: ...

class _ABICallProtocolType(typing.Protocol):
    @typing.overload
    def __call__(  # type: ignore[misc]
        self,
        method: Callable[..., None] | str,
        /,
        *args: object,
        app_id: algopy.Application | algopy.UInt64 | int = ...,
        on_completion: algopy.OnCompleteAction = ...,
        approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        global_num_uint: algopy.UInt64 | int = ...,
        global_num_bytes: algopy.UInt64 | int = ...,
        local_num_uint: algopy.UInt64 | int = ...,
        local_num_bytes: algopy.UInt64 | int = ...,
        extra_program_pages: algopy.UInt64 | int = ...,
        fee: algopy.UInt64 | int = 0,
        sender: algopy.Account | str = ...,
        note: algopy.Bytes | bytes | str = ...,
        rekey_to: algopy.Account | str = ...,
    ) -> algopy.itxn.ApplicationCallInnerTransaction: ...
    @typing.overload
    def __call__(  # type: ignore[misc]
        self,
        method: Callable[..., _TABIResult_co],
        /,
        *args: object,
        app_id: algopy.Application | algopy.UInt64 | int = ...,
        on_completion: algopy.OnCompleteAction = ...,
        approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
        global_num_uint: algopy.UInt64 | int = ...,
        global_num_bytes: algopy.UInt64 | int = ...,
        local_num_uint: algopy.UInt64 | int = ...,
        local_num_bytes: algopy.UInt64 | int = ...,
        extra_program_pages: algopy.UInt64 | int = ...,
        fee: algopy.UInt64 | int = 0,
        sender: algopy.Account | str = ...,
        note: algopy.Bytes | algopy.String | bytes | str = ...,
        rekey_to: algopy.Account | str = ...,
    ) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]: ...
    def __getitem__(
        self, _: type[_TABIResult_co]
    ) -> _ABICallWithReturnProtocol[_TABIResult_co]: ...

abi_call: _ABICallProtocolType = ...
"""
Provides a typesafe way of calling ARC-4 methods via an inner transaction

```python
def abi_call(
    self,
    method: Callable[..., _TABIResult_co] | str,
    /,
    *args: object,
    app_id: algopy.Application | algopy.UInt64 | int = ...,
    on_completion: algopy.OnCompleteAction = ...,
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
    global_num_uint: UInt64 | int = ...,
    global_num_bytes: UInt64 | int = ...,
    local_num_uint: UInt64 | int = ...,
    local_num_bytes: UInt64 | int = ...,
    extra_program_pages: UInt64 | int = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | algopy.String | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]: ...
```
PARAMETERS:  

**method:** The name, method selector or Algorand Python method to call  
**app_id:** Application to call, if 0 or not specified will create a new application  
**on_completion:** OnCompleteAction value for the transaction. If not specified will be inferred from Algorand Python method where possible  
**approval_program:** When creating or updating an application, the approval program  
**clear_state_program:** When creating or updating an application, the clear state program  
**global_num_uint:** When creating an application the number of global uints  
**global_num_bytes:** When creating an application the number of global bytes  
**local_num_uint:** When creating an application the number of local uints  
**local_num_bytes:** When creating an application the number of local bytes  
**extra_program_pages:** When creating an application the The number of extra program pages  
**fee:** The fee to pay for the transaction, defaults to 0  
**sender:** The sender address for the transaction  
**note:** Note to include with the transaction  
**rekey_to:** Account to rekey to  

RETURNS:  
If `method` references an Algorand Contract / Client or the function is indexed with a return type, 
then the result is a tuple containing the ABI result and the inner transaction of the call.  

If no return type is specified, or the method does not have a return value then the result
is the inner transaction of the call.  

Examples:
```
# can reference another algopy contract method
result, txn = abi_call(HelloWorldContract.hello, arc4.String("World"), app=...)
assert result == "Hello, World"

# can reference a method selector
result, txn = abi_call[arc4.String]("hello(string)string", arc4.String("Algo"), app=...)
assert result == "Hello, Algo"

# can reference a method name, the method selector is inferred from arguments and return type
result, txn = abi_call[arc4.String]("hello", "There", app=...)
assert result == "Hello, There"

# calling a method without a return value
txn = abi_call(HelloWorldContract.no_return, arc4.String("World"), app=...)
```
"""

@typing.overload
def arc4_create(  # type: ignore[overload-overlap]
    method: type[ARC4Contract] | Callable[_P, None],
    /,
    *args: object,
    compiled: algopy.CompiledContract = ...,
    on_completion: algopy.OnCompleteAction = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> algopy.itxn.ApplicationCallInnerTransaction: ...
@typing.overload
def arc4_create(
    method: Callable[_P, _TABIResult_co],
    /,
    *args: object,
    compiled: algopy.CompiledContract = ...,
    on_completion: algopy.OnCompleteAction = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]:
    """
    Provides a typesafe and convenient way of creating an ARC4Contract via an inner transaction

    :param method: An ARC-4 create method (ABI or bare), or an ARC4Contract with a single create method
    :param args: ABI args for chosen method
    :param compiled: If supplied will be used to specify transaction parameters required for creation,
                     can be omitted if template variables are not used
    :param on_completion: OnCompleteAction value for the transaction
                          If not specified will be inferred from Algorand Python method where possible
    :param fee: The fee to pay for the transaction, defaults to 0
    :param sender: The sender address for the transaction
    :param note: Note to include with the transaction
    :param rekey_to: Account to rekey to
    """

@typing.overload
def arc4_update(  # type: ignore[overload-overlap]
    method: type[ARC4Contract] | Callable[_P, None],
    /,
    *args: object,
    app_id: algopy.Application | algopy.UInt64 | int,
    compiled: algopy.CompiledContract = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> algopy.itxn.ApplicationCallInnerTransaction: ...
@typing.overload
def arc4_update(
    method: Callable[_P, _TABIResult_co],
    /,
    *args: object,
    app_id: algopy.Application | algopy.UInt64 | int,
    compiled: algopy.CompiledContract = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]:
    """
    Provides a typesafe and convenient way of updating an ARC4Contract via an inner transaction

    :param method: An ARC-4 update method (ABI or bare), or an ARC4Contract with a single update method
    :param args: ABI args for chosen method
    :param app_id: Application to update
    :param compiled: If supplied will be used to specify transaction parameters required for updating,
                     can be omitted if template variables are not used
    :param fee: The fee to pay for the transaction, defaults to 0
    :param sender: The sender address for the transaction
    :param note: Note to include with the transaction
    :param rekey_to: Account to rekey to
    """

@typing.overload
def emit(event: Struct, /) -> None: ...
@typing.overload
def emit(event: str, /, *args: object) -> None: ...
@typing.overload
def emit(event: str | Struct, /, *args: object) -> None:
    """Emit an ARC-28 event for the provided event signature or name, and provided args.

    :param event: Either an ARC-4 Struct, an event name, or event signature.
        * If event is an ARC-4 Struct, the event signature will be determined from the Struct name and fields
        * If event is a signature, then the following args will be typed checked to ensure they match.
        * If event is just a name, the event signature will be inferred from the name and following arguments

    :param args: When event is a signature or name, args will be used as the event data.
    They will all be encoded as single ARC-4 Tuple

    Example:
    ```
    from algopy import ARC4Contract, arc4


    class Swapped(arc4.Struct):
        a: arc4.UInt64
        b: arc4.UInt64


    class EventEmitter(ARC4Contract):
        @arc4.abimethod
        def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
            arc4.emit(Swapped(b, a))
            arc4.emit("Swapped(uint64,uint64)", b, a)
            arc4.emit("Swapped", b, a)
    ```
    """
