# ruff: noqa: A001, E501, F403, PYI021, PYI034, W291
import abc
import typing
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Reversible

import algopy
from algopy import arc4, gtxn, itxn, op
from algopy.arc4 import ARC4Contract
from algopy.op import Global, Txn

__all__ = [
    "arc4",
    "gtxn",
    "itxn",
    "op",
    "ARC4Contract",
    "Global",
    "Txn",
    "UInt64",
    "Bytes",
    "String",
    "BigUInt",
    "ImmutableArray",
    "Array",
    "OnCompleteAction",
    "TransactionType",
    "Account",
    "Asset",
    "Application",
    "Box",
    "BoxRef",
    "BoxMap",
    "CompiledContract",
    "CompiledLogicSig",
    "compile_contract",
    "compile_logicsig",
    "StateTotals",
    "Contract",
    "subroutine",
    "LocalState",
    "GlobalState",
    "urange",
    "uenumerate",
    "OpUpFeeSource",
    "ensure_budget",
    "log",
    "TemplateVar",
    "LogicSig",
    "logicsig",
]

class UInt64:
    """A 64-bit unsigned integer, one of the primary data types on the AVM"""

    __match_value__: int
    __match_args__ = ("__match_value__",)
    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    def __init__(self, value: int = 0, /) -> None:
        """A UInt64 can be initialized with a Python int literal, or an int variable
        declared at the module level"""
    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
    def __eq__(self, other: UInt64 | int) -> bool:  # type: ignore[override]
        """A UInt64 can use the `==` operator with another UInt64 or int"""

    def __ne__(self, other: UInt64 | int) -> bool:  # type: ignore[override]
        """A UInt64 can use the `!=` operator with another UInt64 or int"""

    def __le__(self, other: UInt64 | int) -> bool:
        """A UInt64 can use the `<=` operator with another UInt64 or int"""

    def __lt__(self, other: UInt64 | int) -> bool:
        """A UInt64 can use the `<` operator with another UInt64 or int"""

    def __ge__(self, other: UInt64 | int) -> bool:
        """A UInt64 can use the `>=` operator with another UInt64 or int"""

    def __gt__(self, other: UInt64 | int) -> bool:
        """A UInt64 can use the `>` operator with another UInt64 or int"""
    # truthiness
    def __bool__(self) -> bool:
        """A UInt64 will evaluate to `False` if zero, and `True` otherwise"""
    # ~~~ https://docs.python.org/3/reference/datamodel.html#emulating-numeric-types ~~~
    # +
    def __add__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be added with another UInt64 or int e.g. `UInt(4) + 2`.

        This will error on overflow"""

    def __radd__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be added with another UInt64 or int e.g. `4 + UInt64(2)`.

        This will error on overflow"""

    def __iadd__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be incremented with another UInt64 or int e.g. `a += UInt(2)`.

        This will error on overflow"""
    # -
    def __sub__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be subtracted with another UInt64 or int e.g. `UInt(4) - 2`.

        This will error on underflow"""

    def __rsub__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be subtracted with another UInt64 or int e.g. `4 - UInt64(2)`.

        This will error on underflow"""

    def __isub__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be subtracted with another UInt64 or int e.g. `a -= UInt64(2)`.

        This will error on underflow"""
    # *
    def __mul__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be multiplied with another UInt64 or int e.g. `4 + UInt64(2)`.

        This will error on overflow"""

    def __rmul__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be multiplied with another UInt64 or int e.g. `UInt64(4) + 2`.

        This will error on overflow"""

    def __imul__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be multiplied with another UInt64 or int e.g. `a*= UInt64(2)`.

        This will error on overflow"""
    # //
    def __floordiv__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be floor divided with another UInt64 or int e.g. `UInt64(4) // 2`.

        This will error on divide by zero"""

    def __rfloordiv__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be floor divided with another UInt64 or int e.g. `4 // UInt64(2)`.

        This will error on divide by zero"""

    def __ifloordiv__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be floor divided with another UInt64 or int e.g. `a //= UInt64(2)`.

        This will error on divide by zero"""
    # %
    def __mod__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be modded with another UInt64 or int e.g. `UInt64(4) % 2`.

        This will error on mod by zero"""

    def __rmod__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be modded with another UInt64 or int e.g. `4 % UInt64(2)`.

        This will error on mod by zero"""

    def __imod__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be modded with another UInt64 or int e.g. `a %= UInt64(2)`.

        This will error on mod by zero"""
    # TODO: __divmod__? only supported as single op via divmodw though 🤔
    # **, pow
    def __pow__(self, power: UInt64 | int) -> UInt64:
        """A UInt64 can be raised to the power of another UInt64 or int e.g. `UInt64(4) ** 2`.

        This will error on overflow"""

    def __rpow__(self, power: UInt64 | int) -> UInt64:
        """A UInt64 can be raised to the power of another UInt64 or int e.g. `4 ** UInt64(2)`.

        This will error on overflow"""

    def __ipow__(self, power: UInt64 | int) -> UInt64:
        """A UInt64 can be raised to the power of another UInt64 or int e.g. `a **= UInt64(2)`.

        This will error on overflow"""
    # <<
    def __lshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be left shifted by another UInt64 or int e.g. `UInt64(4) << 2`"""

    def __rlshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be left shifted by another UInt64 or int e.g. `4 << UInt64(2)`"""

    def __ilshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be left shifted by another UInt64 or int e.g. `a <<= UInt64(2)`"""
    # >>
    def __rshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be right shifted by another UInt64 or int e.g. `UInt64(4) >> 2`"""

    def __rrshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be right shifted by another UInt64 or int e.g. `4 >> UInt64(2)`"""

    def __irshift__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can be right shifted by another UInt64 or int e.g. `a >>= UInt64(2)`"""
    # &
    def __and__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise and with another UInt64 or int e.g. `UInt64(4) & 2`"""

    def __rand__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise and with another UInt64 or int e.g. `4 & UInt64(2)`"""

    def __iand__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise and with another UInt64 or int e.g. `a &= UInt64(2)`"""
    # ^
    def __xor__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise xor with another UInt64 or int e.g. `UInt64(4) ^ 2`"""

    def __rxor__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise xor with another UInt64 or int e.g. `4 ^ UInt64(2)`"""

    def __ixor__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise xor with another UInt64 or int e.g. `a ^= UInt64(2)`"""
    # |
    def __or__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise or with another UInt64 or int e.g. `UInt64(4) | 2`"""

    def __ror__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise or with another UInt64 or int e.g. `4 | UInt64(2)`"""

    def __ior__(self, other: UInt64 | int) -> UInt64:
        """A UInt64 can bitwise or with another UInt64 or int e.g. `a |= UInt64(2)`"""
    # ~
    def __invert__(self) -> UInt64:
        """A UInt64 can be bitwise inverted e.g. `~UInt64(4)`"""

    def __index__(self) -> int:
        """A UInt64 can be used in indexing/slice expressions"""

    def __pos__(self) -> UInt64:
        """Supports unary + operator. Redundant given the type is unsigned"""

class Bytes(Reversible[Bytes]):
    """A byte sequence, with a maximum length of 4096 bytes, one of the primary data types on the AVM"""

    __match_value__: bytes
    __match_args__ = ("__match_value__",)
    def __init__(self, value: bytes = b"", /):
        """Bytes can be initialized with a Python bytes literal, or bytes variable
        declared at the module level"""

    @staticmethod
    def from_base32(value: str, /) -> Bytes:
        """Creates Bytes from a base32 encoded string e.g. `Bytes.from_base32("74======")`"""

    @staticmethod
    def from_base64(value: str, /) -> Bytes:
        """Creates Bytes from a base64 encoded string e.g. `Bytes.from_base64("RkY=")`"""

    @staticmethod
    def from_hex(value: str, /) -> Bytes:
        """Creates Bytes from a hex/octal encoded string e.g. `Bytes.from_hex("FF")`"""

    def __add__(self, other: Bytes | bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `Bytes(b"Hello ") + b"World"`."""

    def __radd__(self, other: Bytes | bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `b"Hello " + Bytes(b"World")`."""

    def __iadd__(self, other: Bytes | bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `a += Bytes(b"World")`."""
    # NOTE: __len__ is enforced to return int at runtime (not even a subtype is allowed)
    @property
    def length(self) -> UInt64:
        """Returns the length of the Bytes"""
    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if length of bytes is >0"""

    def __getitem__(
        self, index: UInt64 | int | slice
    ) -> Bytes:  # maps to substring/substring3 if slice, extract/extract3 otherwise?
        """Returns a Bytes containing a single byte if indexed with UInt64 or int
        otherwise the substring o bytes described by the slice"""

    def __iter__(self) -> Iterator[Bytes]:
        """Bytes can be iterated, yielding each consecutive byte"""

    def __reversed__(self) -> Iterator[Bytes]:
        """Bytes can be iterated in reverse, yield each preceding byte starting at the end"""
    # mypy suggests due to Liskov below should be other: object
    # need to consider ramifications here, ignoring it for now
    def __eq__(self, other: Bytes | bytes) -> bool:  # type: ignore[override]
        """Bytes can be compared using the `==` operator with another Bytes or bytes"""

    def __ne__(self, other: Bytes | bytes) -> bool:  # type: ignore[override]
        """Bytes can be compared using the `!=` operator with another Bytes or bytes"""
    # bitwise operators
    # &
    def __and__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise and with another Bytes or bytes e.g. `Bytes(b"FF") & b"0F")`"""

    def __iand__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise and with another Bytes or bytes e.g. `a &= Bytes(b"0F")`"""
    # ^
    def __xor__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise xor with another Bytes or bytes e.g. `Bytes(b"FF") ^ b"0F")`"""

    def __ixor__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise xor with another Bytes or bytes e.g. `a ^= Bytes(b"0F")`"""
    # |
    def __or__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise or with another Bytes or bytes e.g. `Bytes(b"FF") | b"0F")`"""

    def __ior__(self, other: Bytes | bytes) -> Bytes:
        """Bytes can bitwise or with another Bytes or bytes e.g. `a |= Bytes(b"0F")`"""
    # ~
    def __invert__(self) -> Bytes:
        """Bytes can be bitwise inverted e.g. `~Bytes(b"FF)`"""

    def __contains__(self, other: Bytes | bytes) -> bool:
        """Test whether another Bytes is a substring of this one.
        Note this is expensive due to a lack of AVM support."""

class String(Container[String]):
    """A UTF-8 encoded string.

    In comparison to `arc4.String`, this type does not store the array length prefix, since that
    information is always available through the `len` AVM op. This makes it more efficient to
    operate on when doing operations such as concatenation.

    Note that due to the lack of UTF-8 support in the AVM, indexing and length operations are not
    currently supported.
    """

    __match_value__: str
    __match_args__ = ("__match_value__",)
    def __init__(self, value: str = "", /):
        """A String can be initialized with a Python `str` literal, or a `str` variable
        declared at the module level"""
    def __add__(self, other: String | str) -> String:
        """Concatenate `String` with another `String` or `str` literal
        e.g. `String("Hello ") + "World"`."""
    def __radd__(self, other: String | str) -> String:
        """Concatenate String with another `String` or `str` literal
        e.g. `"Hello " + String("World")`."""
    def __iadd__(self, other: String | str) -> String:
        """Concatenate `String` with another `String` or `str` literal
        e.g. `a = String("Hello"); a += "World"`."""
    def __bool__(self) -> bool:
        """Returns `True` if the string is not empty"""
    def __eq__(self, other: String | str) -> bool:  # type: ignore[override]
        """Supports using the `==` operator with another `String` or literal `str`"""
    def __ne__(self, other: String | str) -> bool:  # type: ignore[override]
        """Supports using the `!=` operator with another `String` or literal `str`"""
    def __contains__(self, other: String | str) -> bool:  # type: ignore[override]
        """Test whether another string is a substring of this one.
        Note this is expensive due to a lack of AVM support."""
    def startswith(self, prefix: String | str) -> bool:
        """Check if this string starts with another string.

        The behaviour should mirror `str.startswith`, for example, if `prefix` is the empty string,
        the result will always be `True`.

        Only a single argument is currently supported.
        """
    def endswith(self, suffix: String | str) -> bool:
        """Check if this string ends with another string.

        The behaviour should mirror `str.endswith`, for example, if `suffix` is the empty string,
        the result will always be `True`.

        Only a single argument is currently supported.
        """
    def join(self, others: tuple[String | str, ...], /) -> String:
        """Join a sequence of Strings with a common separator.

        The behaviour should mirror `str.join`.
        """
    """Represents a type that is a single bytes value"""
    @classmethod
    def from_bytes(cls, value: Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""

class BigUInt:
    """A variable length (max 512-bit) unsigned integer"""

    __match_value__: int
    __match_args__ = ("__match_value__",)
    def __init__(self, value: UInt64 | int = 0, /) -> None:
        """A BigUInt can be initialized with a UInt64, a Python int literal, or an int variable
        declared at the module level"""
    def __eq__(self, other: BigUInt | UInt64 | int) -> bool:  # type: ignore[override]
        """A BigUInt can use the `==` operator with another BigUInt, UInt64 or int"""
    def __ne__(self, other: BigUInt | UInt64 | int) -> bool:  # type: ignore[override]
        """A BigUInt can use the `!=` operator with another BigUInt, UInt64 or int"""
    def __le__(self, other: BigUInt | UInt64 | int) -> bool:
        """A BigUInt can use the `<=` operator with another BigUInt, UInt64 or int"""
    def __lt__(self, other: BigUInt | UInt64 | int) -> bool:
        """A BigUInt can use the `<` operator with another BigUInt, UInt64 or int"""
    def __ge__(self, other: BigUInt | UInt64 | int) -> bool:
        """A BigUInt can use the `>=` operator with another BigUInt, UInt64 or int"""
    def __gt__(self, other: BigUInt | UInt64 | int) -> bool:
        """A BigUInt can use the `>` operator with another BigUInt, UInt64 or int"""
    def __bool__(self) -> bool:
        """A BigUInt will evaluate to `False` if zero, and `True` otherwise"""
    def __add__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be added with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`."""
    def __radd__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be added with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`."""
    def __iadd__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be incremented with another BigUInt, UInt64 or int e.g. `a += BigUInt(2)`."""
    def __sub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `BigUInt(4) - 2`.

        This will error on underflow"""
    def __rsub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `4 - BigUInt(2)`.

        This will error on underflow"""
    def __isub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `a -= BigUInt(2)`.

        This will error on underflow"""
    def __mul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`."""
    def __rmul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`."""
    def __imul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `a*= BigUInt(2)`."""
    def __floordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `BigUInt(4) // 2`.

        This will error on divide by zero"""
    def __rfloordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `4 // BigUInt(2)`.

        This will error on divide by zero"""
    def __ifloordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `a //= BigUInt(2)`.

        This will error on divide by zero"""
    def __mod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `BigUInt(4) % 2`.

        This will error on mod by zero"""
    def __rmod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `4 % BigUInt(2)`.

        This will error on mod by zero"""
    def __imod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `a %= BigUInt(2)`.

        This will error on mod by zero"""
    def __and__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `BigUInt(4) & 2`"""
    def __rand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `4 & BigUInt(2)`"""
    def __iand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `a &= BigUInt(2)`"""
    def __xor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `BigUInt(4) ^ 2`"""
    def __rxor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `4 ^ BigUInt(2)`"""
    def __ixor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `a ^= BigUInt(2)`"""
    def __or__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `BigUInt(4) | 2`"""
    def __ror__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `4 | BigUInt(2)`"""
    def __ior__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `a |= BigUInt(2)`"""
    def __pos__(self) -> BigUInt:
        """Supports unary + operator. Redundant given the type is unsigned"""
    """Represents a type that is a single bytes value"""
    @classmethod
    def from_bytes(cls, value: Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""

_T = typing.TypeVar("_T")

class ImmutableArray(Reversible[_T]):
    """
    An immutable array that supports fixed and dynamically sized immutable elements.
    Modifications are done by returning a new copy of the array with the modifications applied.

    Example: ::

        arr = ImmutableArray[UInt64]()

        arr = arr.append(UInt64(42))
        element = arr[0]
        assert element == 42
        arr = arr.pop()
    """

    def __init__(self, *items: _T):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _T:
        """Gets the item of the array at provided index"""

    def replace(self, index: algopy.UInt64 | int, value: _T) -> typing.Self:
        """Returns a copy of the array with the item at specified index replaced with the specified value"""

    def append(self, item: _T, /) -> typing.Self:
        """Return a copy of the array with a another value appended to the end"""

    def __add__(self, other: Iterable[_T], /) -> typing.Self:
        """Return a copy of this array extended with the contents of another array"""

    def pop(self) -> typing.Self:
        """Return a copy of this array with the last item removed"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

class Array(Reversible[_T]):
    """
    A mutable array that supports fixed sized immutable elements. All references to this array
    will see any updates made to it.

    These arrays may use scratch slots if required. If a contract also needs to use scratch slots
    for other purposes then they should be reserved using the `scratch_slots` parameter
    in [`algopy.Contract`](#algopy.Contract),
    [`algopy.arc4.ARC4Contract`](#algopy.arc4.ARC4Contract) or [`algopy.logicsig`](#algopy.logicsig)
    """

    def __init__(self, *items: _T):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _T:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _T) -> _T:
        """Sets the item of the array at specified index to provided value"""

    def append(self, item: _T, /) -> None:
        """Append an item to this array"""

    def extend(self, other: Iterable[_T], /) -> None:
        """Extend this array with the contents of another array"""

    def pop(self) -> _T:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def freeze(self) -> ImmutableArray[_T]:
        """Returns an immutable copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

@typing.final
class OnCompleteAction(UInt64):
    """On Completion actions available in an application call transaction"""

    NoOp: OnCompleteAction = ...
    """NoOP indicates that no additional action is performed when the transaction completes"""

    OptIn: OnCompleteAction = ...
    """OptIn indicates that an application transaction will allocate some
    LocalState for the application in the sender's account"""

    CloseOut: OnCompleteAction = ...
    """CloseOut indicates that an application transaction will deallocate
    some LocalState for the application from the user's account"""

    ClearState: OnCompleteAction = ...
    """ClearState is similar to CloseOut, but may never fail. This
    allows users to reclaim their minimum balance from an application
    they no longer wish to opt in to."""

    UpdateApplication: OnCompleteAction = ...
    """UpdateApplication indicates that an application transaction will
    update the ApprovalProgram and ClearStateProgram for the application"""

    DeleteApplication: OnCompleteAction = ...
    """DeleteApplication indicates that an application transaction will
    delete the AppParams for the application from the creator's balance
    record"""

@typing.final
class TransactionType(UInt64):
    """The different transaction types available in a transaction"""

    Payment: TransactionType = ...
    """A Payment transaction"""
    KeyRegistration: TransactionType = ...
    """A Key Registration transaction"""
    AssetConfig: TransactionType = ...
    """An Asset Config transaction"""
    AssetTransfer: TransactionType = ...
    """An Asset Transfer transaction"""
    AssetFreeze: TransactionType = ...
    """An Asset Freeze transaction"""
    ApplicationCall: TransactionType = ...
    """An Application Call transaction"""

class Account:
    """An Account on the Algorand network.

    Note: must be an available resource to access properties other than `bytes`
    """

    __match_value__: str
    __match_args__ = ("__match_value__",)
    def __init__(self, value: str | Bytes = ..., /):
        """
        If `value` is a string, it should be a 58 character base32 string,
        ie a base32 string-encoded 32 bytes public key + 4 bytes checksum.
        If `value` is a Bytes, it's length checked to be 32 bytes - to avoid this
        check, use `Address.from_bytes(...)` instead.
        Defaults to the zero-address.
        """
    def __eq__(self, other: Account | str) -> bool:  # type: ignore[override]
        """Account equality is determined by the address of another `Account` or `str`"""
    def __ne__(self, other: Account | str) -> bool:  # type: ignore[override]
        """Account equality is determined by the address of another `Account` or `str`"""
    def __bool__(self) -> bool:
        """Returns `True` if not equal to the zero-address"""
    @property
    def balance(self) -> UInt64:
        """Account balance in microalgos

        .. note::
            Account must be an available resource
        """
    @property
    def min_balance(self) -> UInt64:
        """Minimum required balance for account, in microalgos

        .. note::
            Account must be an available resource
        """
    @property
    def auth_address(self) -> Account:
        """Address the account is rekeyed to

        .. note::
            Account must be an available resource
        """
    @property
    def total_num_uint(self) -> UInt64:
        """The total number of uint64 values allocated by this account in Global and Local States.

        .. note::
            Account must be an available resource
        """
    @property
    def total_num_byte_slice(self) -> UInt64:
        """The total number of byte array values allocated by this account in Global and Local States.

        .. note::
            Account must be an available resource
        """
    @property
    def total_extra_app_pages(self) -> UInt64:
        """The number of extra app code pages used by this account.

        .. note::
            Account must be an available resource
        """
    @property
    def total_apps_created(self) -> UInt64:
        """The number of existing apps created by this account.

        .. note::
            Account must be an available resource
        """
    @property
    def total_apps_opted_in(self) -> UInt64:
        """The number of apps this account is opted into.

        .. note::
            Account must be an available resource
        """
    @property
    def total_assets_created(self) -> UInt64:
        """The number of existing ASAs created by this account.

        .. note::
            Account must be an available resource
        """
    @property
    def total_assets(self) -> UInt64:
        """The numbers of ASAs held by this account (including ASAs this account created).

        .. note::
            Account must be an available resource
        """
    @property
    def total_boxes(self) -> UInt64:
        """The number of existing boxes created by this account's app.

        .. note::
            Account must be an available resource
        """
    @property
    def total_box_bytes(self) -> UInt64:
        """The total number of bytes used by this account's app's box keys and values.

        .. note::
            Account must be an available resource
        """
    def is_opted_in(self, asset_or_app: Asset | Application, /) -> bool:
        """Returns true if this account is opted in to the specified Asset or Application.

        .. note::
            Account and Asset/Application must be an available resource
        """
    """Represents a type that is a single bytes value"""
    @classmethod
    def from_bytes(cls, value: Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""

@typing.final
class Asset:
    """An Asset on the Algorand network."""

    def __init__(self, asset_id: UInt64 | int = 0, /):
        """Initialized with the id of an asset. Defaults to zero (an invalid ID)."""

    @property
    def id(self) -> UInt64:
        """Returns the id of the Asset"""

    def __eq__(self, other: Asset) -> bool:  # type: ignore[override]
        """Asset equality is determined by the equality of an Asset's id"""

    def __ne__(self, other: Asset) -> bool:  # type: ignore[override]
        """Asset equality is determined by the equality of an Asset's id"""

    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if `asset_id` is not `0`"""

    @property
    def total(self) -> UInt64:
        """Total number of units of this asset

        .. note::
            Asset must be an available resource
        """

    @property
    def decimals(self) -> UInt64:
        """See AssetParams.Decimals

        .. note::
            Asset must be an available resource
        """

    @property
    def default_frozen(self) -> bool:
        """Frozen by default or not

        .. note::
            Asset must be an available resource
        """

    @property
    def unit_name(self) -> Bytes:
        """Asset unit name

        .. note::
            Asset must be an available resource
        """

    @property
    def name(self) -> Bytes:
        """Asset name

        .. note::
            Asset must be an available resource
        """

    @property
    def url(self) -> Bytes:
        """URL with additional info about the asset

        .. note::
            Asset must be an available resource
        """

    @property
    def metadata_hash(self) -> Bytes:
        """Arbitrary commitment

        .. note::
            Asset must be an available resource
        """

    @property
    def manager(self) -> Account:
        """Manager address

        .. note::
            Asset must be an available resource
        """

    @property
    def reserve(self) -> Account:
        """Reserve address

        .. note::
            Asset must be an available resource
        """

    @property
    def freeze(self) -> Account:
        """Freeze address

        .. note::
            Asset must be an available resource
        """

    @property
    def clawback(self) -> Account:
        """Clawback address

        .. note::
            Asset must be an available resource
        """

    @property
    def creator(self) -> Account:
        """Creator address

        .. note::
            Asset must be an available resource
        """

    def balance(self, account: Account, /) -> UInt64:
        """Amount of the asset unit held by this account. Fails if the account has not
        opted in to the asset.

        .. note::
            Asset and supplied Account must be an available resource
        """

    def frozen(self, account: Account, /) -> bool:
        """Is the asset frozen or not. Fails if the account has not
        opted in to the asset.

        .. note::
            Asset and supplied Account must be an available resource
        """

@typing.final
class Application:
    """An Application on the Algorand network."""

    def __init__(self, application_id: UInt64 | int = 0, /):
        """Initialized with the id of an application. Defaults to zero (an invalid ID)."""

    @property
    def id(self) -> UInt64:
        """Returns the id of the application"""

    def __eq__(self, other: Application) -> bool:  # type: ignore[override]
        """Application equality is determined by the equality of an Application's id"""

    def __ne__(self, other: Application) -> bool:  # type: ignore[override]
        """Application equality is determined by the equality of an Application's id"""

    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if `application_id` is not `0`"""

    @property
    def approval_program(self) -> Bytes:
        """Bytecode of Approval Program

        .. note::
            Application must be an available resource
        """

    @property
    def clear_state_program(self) -> Bytes:
        """Bytecode of Clear State Program

        .. note::
            Application must be an available resource
        """

    @property
    def global_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Global State

        .. note::
            Application must be an available resource
        """

    @property
    def global_num_bytes(self) -> UInt64:
        """Number of byte array values allowed in Global State

        .. note::
            Application must be an available resource
        """

    @property
    def local_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Local State

        .. note::
            Application must be an available resource
        """

    @property
    def local_num_bytes(self) -> UInt64:
        """Number of byte array values allowed in Local State

        .. note::
            Application must be an available resource
        """

    @property
    def extra_program_pages(self) -> UInt64:
        """Number of Extra Program Pages of code space

        .. note::
            Application must be an available resource
        """

    @property
    def creator(self) -> Account:
        """Creator address

        .. note::
            Application must be an available resource
        """

    @property
    def address(self) -> Account:
        """Address for which this application has authority

        .. note::
            Application must be an available resource
        """

_TKey = typing.TypeVar("_TKey")
_TValue = typing.TypeVar("_TValue")

@typing.final
class Box(typing.Generic[_TValue]):
    """
    Box abstracts the reading and writing of a single value to a single box.
    The box size will be reconfigured dynamically to fit the size of the value being assigned to
    it.
    """

    def __init__(
        self, type_: type[_TValue], /, *, key: bytes | str | Bytes | String = ...
    ) -> None: ...
    def __bool__(self) -> bool:
        """
        Returns True if the box exists, regardless of the truthiness of the contents
        of the box
        """

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    @property
    def value(self) -> _TValue:
        """Retrieve the contents of the box. Fails if the box has not been created."""

    @value.setter
    def value(self, value: _TValue) -> None:
        """Write _value_ to the box. Creates the box if it does not exist."""

    @value.deleter
    def value(self) -> None:
        """Delete the box"""

    def get(self, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents of the box, or return the default value if the box has not been
        created.

        :arg default: The default value to return if the box has not been created
        """

    def maybe(self) -> tuple[_TValue, bool]:
        """
        Retrieve the contents of the box if it exists, and return a boolean indicating if the box
        exists.

        """

    @property
    def length(self) -> UInt64:
        """
        Get the length of this Box. Fails if the box does not exist
        """

@typing.final
class BoxRef:
    """
    BoxRef abstracts the reading and writing of boxes containing raw binary data. The size is
    configured manually, and can be set to values larger than what the AVM can handle in a single
    value.
    """

    def __init__(self, /, *, key: bytes | str | Bytes | String = ...) -> None: ...
    def __bool__(self) -> bool:
        """Returns True if the box has a value set, regardless of the truthiness of that value"""

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    def create(self, *, size: UInt64 | int) -> bool:
        """
        Creates a box with the specified size, setting all bits to zero. Fails if the box already
        exists with a different size. Fails if the specified size is greater than the max box size
        (32,768)

        Returns True if the box was created, False if the box already existed
        """

    def delete(self) -> bool:
        """
        Deletes the box if it exists and returns a value indicating if the box existed
        """

    def extract(self, start_index: UInt64 | int, length: UInt64 | int) -> Bytes:
        """
        Extract a slice of bytes from the box.

        Fails if the box does not exist, or if `start_index + length > len(box)`

        :arg start_index: The offset to start extracting bytes from
        :arg length: The number of bytes to extract
        """

    def resize(self, new_size: UInt64 | int) -> None:
        """
        Resizes the box the specified `new_size`. Truncating existing data if the new value is
        shorter or padding with zero bytes if it is longer.

        :arg new_size: The new size of the box
        """

    def replace(self, start_index: UInt64 | int, value: Bytes | bytes) -> None:
        """
        Write `value` to the box starting at `start_index`. Fails if the box does not exist,
        or if `start_index + len(value) > len(box)`

        :arg start_index: The offset to start writing bytes from
        :arg value: The bytes to be written
        """

    def splice(
        self, start_index: UInt64 | int, length: UInt64 | int, value: Bytes | bytes
    ) -> None:
        """
        set box to contain its previous bytes up to index `start_index`, followed by `bytes`,
        followed by the original bytes of the box that began at index `start_index + length`

        **Important: This op does not resize the box**
        If the new value is longer than the box size, it will be truncated.
        If the new value is shorter than the box size, it will be padded with zero bytes

        :arg start_index: The index to start inserting `value`
        :arg length: The number of bytes after `start_index` to omit from the new value
        :arg value: The `value` to be inserted.
        """

    def get(self, *, default: Bytes | bytes) -> Bytes:
        """
        Retrieve the contents of the box, or return the default value if the box has not been
        created.

        :arg default: The default value to return if the box has not been created
        """

    def put(self, value: Bytes | bytes) -> None:
        """
        Replaces the contents of box with value. Fails if box exists and len(box) != len(value).
        Creates box if it does not exist

        :arg value: The value to write to the box
        """

    def maybe(self) -> tuple[Bytes, bool]:
        """
        Retrieve the contents of the box if it exists, and return a boolean indicating if the box
        exists.
        """

    @property
    def length(self) -> UInt64:
        """
        Get the length of this Box. Fails if the box does not exist
        """

@typing.final
class BoxMap(typing.Generic[_TKey, _TValue]):
    """
    BoxMap abstracts the reading and writing of a set of boxes using a common key and content type.
    Each composite key (prefix + key) still needs to be made available to the application via the
    `boxes` property of the Transaction.
    """

    def __init__(
        self,
        key_type: type[_TKey],
        value_type: type[_TValue],
        /,
        *,
        key_prefix: bytes | str | Bytes | String = ...,
    ) -> None:
        """Declare a box map.

        :arg key_type: The type of the keys
        :arg value_type: The type of the values
        :arg key_prefix: The value used as a prefix to key data, can be empty.
                         When the BoxMap is being assigned to a member variable,
                         this argument is optional and defaults to the member variable name,
                         and if a custom value is supplied it must be static.
        """

    @property
    def key_prefix(self) -> Bytes:
        """Provides access to the raw storage key-prefix"""

    def __getitem__(self, key: _TKey) -> _TValue:
        """
        Retrieve the contents of a keyed box. Fails if the box for the key has not been created.
        """

    def __setitem__(self, key: _TKey, value: _TValue) -> None:
        """Write _value_ to a keyed box. Creates the box if it does not exist"""

    def __delitem__(self, key: _TKey) -> None:
        """Deletes a keyed box"""

    def __contains__(self, key: _TKey) -> bool:
        """
        Returns True if a box with the specified key exists in the map, regardless of the
        truthiness of the contents of the box
        """

    def get(self, key: _TKey, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents of a keyed box, or return the default value if the box has not been
        created.

        :arg key: The key of the box to get
        :arg default: The default value to return if the box has not been created.
        """

    def maybe(self, key: _TKey) -> tuple[_TValue, bool]:
        """
        Retrieve the contents of a keyed box if it exists, and return a boolean indicating if the
        box exists.

        :arg key: The key of the box to get
        """

    def length(self, key: _TKey) -> UInt64:
        """
        Get the length of an item in this BoxMap. Fails if the box does not exist

        :arg key: The key of the box to get
        """

@typing.final
class CompiledContract(typing.NamedTuple):
    """
    Provides compiled programs and state allocation values for a Contract.
    Create by calling [`compile_contract`](#algopy.compile_contract).
    """

    approval_program: tuple[Bytes, Bytes]
    """
    Approval program pages for a contract, after template variables have been replaced
    and compiled to AVM bytecode
    """

    clear_state_program: tuple[Bytes, Bytes]
    """
    Clear state program pages for a contract, after template variables have been replaced
    and compiled to AVM bytecode
    """

    extra_program_pages: UInt64
    """
    By default, provides extra program pages required based on approval and clear state program
    size, can be overridden when calling compile_contract
    """

    global_uints: UInt64
    """
    By default, provides global num uints based on contract state totals, can be overridden
    when calling compile_contract
    """

    global_bytes: UInt64
    """
    By default, provides global num bytes based on contract state totals, can be overridden
    when calling compile_contract
    """

    local_uints: UInt64
    """
    By default, provides local num uints based on contract state totals, can be overridden
    when calling compile_contract
    """

    local_bytes: UInt64
    """
    By default, provides local num bytes based on contract state totals, can be overridden
    when calling compile_contract
    """

@typing.final
class CompiledLogicSig(typing.NamedTuple):
    """
    Provides account for a Logic Signature.
    Create by calling [`compile_logicsig`](#algopy.compile_logicsig).
    """

    account: Account
    """
    Address of a logic sig program, after template variables have been replaced and compiled
    to AVM bytecode
    """

def compile_contract(
    contract: type[Contract],
    /,
    *,
    extra_program_pages: UInt64 | int = ...,
    global_uints: UInt64 | int = ...,
    global_bytes: UInt64 | int = ...,
    local_uints: UInt64 | int = ...,
    local_bytes: UInt64 | int = ...,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledContract:
    """
    Returns the compiled data for the specified contract

    :param contract: Algorand Python Contract to compile
    :param extra_program_pages: Number of extra program pages, defaults to minimum required for contract
    :param global_uints: Number of global uint64s, defaults to value defined for contract
    :param global_bytes: Number of global bytes, defaults to value defined for contract
    :param local_uints: Number of local uint64s, defaults to value defined for contract
    :param local_bytes: Number of local bytes, defaults to value defined for contract
    :param template_vars: Template variables to substitute into the contract,
                          key should be without the prefix, must evaluate to a compile time constant
                          and match the type of the template var declaration
    :param template_vars_prefix: Prefix to add to provided template vars,
                   defaults to the prefix supplied on command line (which defaults to ``"TMPL_"``)
    """

def compile_logicsig(
    logicsig: LogicSig,
    /,
    *,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledLogicSig:
    """
    Returns the Account for the specified logic signature

    :param logicsig: Algorand Python Logic Signature to compile
    :param template_vars: Template variables to substitute into the logic signature,
                          key should be without the prefix, must evaluate to a compile time constant
                          and match the type of the template var declaration
    :param template_vars_prefix: Prefix to add to provided template vars,
                                 defaults to the prefix supplied on command line (which defaults to ``"TMPL_"``)
    """
@typing.final
class StateTotals:
    """
    Options class to manually define the total amount of global and local state contract will use,
    used by [`Contract.__init_subclass__`](#algopy.Contract.__init_subclass__).

    This is not required when all state is assigned to `self.`, but is required if a
    contract dynamically interacts with state via `AppGlobal.get_bytes` etc, or if you want
    to reserve additional state storage for future contract updates, since the Algorand protocol
    doesn't allow increasing them after creation.
    """

    def __init__(
        self,
        *,
        global_uints: int = ...,
        global_bytes: int = ...,
        local_uints: int = ...,
        local_bytes: int = ...,
    ) -> None:
        """Specify the totals for both global and local, and for each type. Any arguments not
        specified default to their automatically calculated values.

        Values are validated against the known totals assigned through `self.`, a warning is
        produced if the total specified is insufficient to accommodate all `self.` state values
        at once.
        """

class Contract(abc.ABC):
    """Base class for an Algorand Smart Contract"""

    def __init_subclass__(
        cls,
        *,
        name: str = ...,
        scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = ...,
        state_totals: StateTotals = ...,
        avm_version: int = ...,
    ):
        """
        When declaring a Contract subclass, options and configuration are passed in
        the base class list: ::

            class MyContract(algopy.Contract, name="CustomName"):
                ...

        :param name:
         Will affect the output TEAL file name if there are multiple non-abstract contracts
         in the same file.

         If the contract is a subclass of algopy.ARC4Contract, `name` will also be used as the
         contract name in the ARC-32 application.json, instead of the class name.

        :param scratch_slots:
         Allows you to mark a slot ID or range of slot IDs as "off limits" to Puya.
         These slot ID(s) will never be written to or otherwise manipulating by the compiler itself.
         This is particularly useful in combination with `algopy.op.gload_bytes` / `algopy.op.gload_uint64`
         which lets a contract in a group transaction read from the scratch slots of another contract
         that occurs earlier in the transaction group.

         In the case of inheritance, scratch slots reserved become cumulative. It is not an error
         to have overlapping ranges or values either, so if a base class contract reserves slots
         0-5 inclusive and the derived contract reserves 5-10 inclusive, then within the derived
         contract all slots 0-10 will be marked as reserved.

        :param state_totals:
         Allows defining what values should be used for global and local uint and bytes storage
         values when creating a contract. Used when outputting ARC-32 application.json schemas.

         If let unspecified, the totals will be determined by the compiler based on state
         variables assigned to `self`.

         This setting is not inherited, and only applies to the exact `Contract` it is specified
         on. If a base class does specify this setting, and a derived class does not, a warning
         will be emitted for the derived class. To resolve this warning, `state_totals` must be
         specified. Note that it is valid to not provide any arguments to the `StateTotals`
         constructor, like so `state_totals=StateTotals()`, in which case all values will be
         automatically calculated.
        :param avm_version:
         Determines which AVM version to use, this affects what operations are supported.
         Defaults to value provided supplied on command line (which defaults to current mainnet version)
        """

    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool:
        """Represents the program called for all transactions
        where `OnCompletion` != `ClearState`"""

    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool:
        """Represents the program called when `OnCompletion` == `ClearState`"""

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")

@typing.overload
def subroutine(sub: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def subroutine(
    *, inline: bool | typing.Literal["auto"] = "auto"
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """
    Decorator to indicate functions or methods that can be called by a Smart Contract

    Inlining can be controlled with the decorator argument `inline`.
    When unspecified it defaults to auto, which allows the optimizer to decide whether to inline
    or not. Setting `inline=True` forces inlining, and `inline=False` ensures the function will
    never be inlined.
    """

_TState = typing.TypeVar("_TState")

@typing.final
class LocalState(typing.Generic[_TState]):
    """Local state associated with the application and an account"""

    def __init__(
        self: LocalState[_TState],
        type_: type[_TState],
        /,
        *,
        key: String | Bytes | bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the local state key and it's associated type

        ::

            self.names = LocalState(algopy.Bytes)
        """

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    def __getitem__(self, account: Account | UInt64 | int) -> _TState:
        """Data can be accessed by an `Account` reference or foreign account index

        ::

            account_name = self.names[account]
        """

    def __setitem__(self, account: Account | UInt64 | int, value: _TState) -> None:
        """Data can be stored by using an `Account` reference or foreign account index

        ::

            self.names[account] = account_name
        """

    def __delitem__(self, account: Account | UInt64 | int) -> None:
        """Data can be removed by using an `Account` reference or foreign account index

        ::

            del self.names[account]
        """

    def __contains__(self, account: Account | UInt64 | int) -> bool:
        """Can test if data exists by using an `Account` reference or foreign account index

        ::

            assert account in self.names
        """

    def get(self, account: Account | UInt64 | int, default: _TState) -> _TState:
        """Can retrieve value using an `Account` reference or foreign account index,
        and a fallback default value.

        ::

            name = self.names.get(account, Bytes(b"no name")
        """

    def maybe(self, account: Account | UInt64 | int) -> tuple[_TState, bool]:
        """Can retrieve value, and a bool indicating if the value was present
        using an `Account` reference or foreign account index.

        ::

            name, name_exists = self.names.maybe(account)
            if not name_exists:
                name = Bytes(b"no name")
        """

@typing.final
class GlobalState(typing.Generic[_TState]):
    """Global state associated with the application, the key will be the name of the member, this
    is assigned to

    .. note::
        The `GlobalState` class provides a richer API that in addition to storing and retrieving
        values, can test if a value is set or unset it. However if this extra functionality is not
        needed then it is simpler to just store the data without the GlobalState proxy
        e.g. `self.some_variable = UInt64(0)`
    """

    @typing.overload
    def __init__(
        self: GlobalState[_TState],
        type_: type[_TState],
        /,
        *,
        key: String | Bytes | bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the global state key and its type without initializing its value"""

    @typing.overload
    def __init__(
        self: GlobalState[_TState],
        initial_value: _TState,
        /,
        *,
        key: bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the global state key and initialize its value"""

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    @property
    def value(self) -> _TState:
        """Returns the value or and error if the value is not set

        ::

            name = self.name.value
        """

    @value.setter
    def value(self, value: _TState) -> None:
        """Sets the value

        ::

            self.name.value = Bytes(b"Alice")
        """

    @value.deleter
    def value(self) -> None:
        """Removes the value

        ::

            del self.name.value
        """

    def __bool__(self) -> bool:
        """Returns `True` if the key has a value set, regardless of the truthiness of that value"""

    def get(self, default: _TState) -> _TState:
        """Returns the value or `default` if no value is set

        ::

            name = self.name.get(Bytes(b"no name")
        """

    def maybe(self) -> tuple[_TState, bool]:
        """Returns the value, and a bool

        ::

            name, name_exists = self.name.maybe()
            if not name_exists:
                name = Bytes(b"no name")
        """

@typing.final
class urange(Reversible[UInt64]):  # noqa: N801
    """Produces a sequence of UInt64 from start (inclusive) to stop (exclusive) by step.

    urange(4) produces 0, 1, 2, 3
    urange(i, j) produces i, i+1, i+2, ..., j-1.
    urange(i, j, 2) produces i, i+2, i+4, ..., i+2n where n is the largest value where i+2n < j
    """

    @typing.overload
    def __init__(self, stop: int | UInt64, /) -> None: ...
    @typing.overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, /) -> None: ...
    @typing.overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, step: int | UInt64, /) -> None: ...
    def __iter__(self) -> Iterator[UInt64]: ...
    def __reversed__(self) -> Iterator[UInt64]: ...

@typing.final
class uenumerate(Reversible[tuple[UInt64, _T]]):  # noqa: N801
    """Yields pairs containing a count (from zero) and a value yielded by the iterable argument.

    enumerate is useful for obtaining an indexed list:
        (0, seq[0]), (1, seq[1]), (2, seq[2]), ...

    enumerate((a, b, c)) produces (0, a), (1, b), (2, c)
    """

    def __init__(self, iterable: Iterable[_T]): ...
    def __iter__(self) -> Iterator[tuple[UInt64, _T]]: ...
    def __reversed__(self) -> Iterator[tuple[UInt64, _T]]: ...

@typing.final
class OpUpFeeSource(UInt64):
    """Defines the source of fees for the OpUp utility."""

    GroupCredit: OpUpFeeSource = ...
    """Only the excess fee (credit) on the outer group should be used (set inner_tx.fee=0)"""
    AppAccount: OpUpFeeSource = ...
    """The app's account will cover all fees (set inner_tx.fee=Global.min_tx_fee())"""
    Any: OpUpFeeSource = ...
    """First the excess will be used, remaining fees will be taken from the app account"""

def ensure_budget(required_budget: UInt64 | int, fee_source: OpUpFeeSource = ...) -> None:
    """Ensure the available op code budget is greater than or equal to required_budget"""

def log(*args: object, sep: String | str | Bytes | bytes = "") -> None:
    """Concatenates and logs supplied args as a single bytes value.

    UInt64 args are converted to bytes and each argument is separated by `sep`.
    Literal `str` values will be encoded as UTF8.
    """

_T_co = typing.TypeVar("_T_co", covariant=True)

class _TemplateVarMethod(typing.Protocol[_T_co]):
    def __call__(self, variable_name: str, /, *, prefix: str = "TMPL_") -> _T_co: ...

class _TemplateVarGeneric(typing.Protocol):
    def __getitem__(self, _: type[_T_co]) -> _TemplateVarMethod[_T_co]: ...

TemplateVar: _TemplateVarGeneric = ...
"""Template variables can be used to represent a placeholder for a deploy-time provided value."""

@typing.final
class LogicSig:
    """A logic signature"""

@typing.overload
def logicsig(sub: Callable[[], bool | UInt64], /) -> LogicSig: ...
@typing.overload
def logicsig(
    *,
    name: str = ...,
    avm_version: int = ...,
    scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = (),
) -> Callable[[Callable[[], bool | UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature"""
