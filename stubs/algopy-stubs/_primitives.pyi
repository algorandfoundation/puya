# ruff: noqa: PYI034
import typing
from collections.abc import Container, Iterator, Reversible

from algopy._interfaces import _Validatable

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

class _BytesBase(typing.Protocol, Reversible[Bytes]):
    """A byte sequence, with a maximum length of 4096 bytes, one of the primary data types on the AVM"""

    @classmethod
    def from_base32(cls, value: str, /) -> typing.Self:
        """Creates an instance from a base32 encoded string"""

    @classmethod
    def from_base64(cls, value: str, /) -> typing.Self:
        """Creates an instance from a base64 encoded string"""

    @classmethod
    def from_hex(cls, value: str, /) -> typing.Self:
        """Creates an instance from a hex/octal encoded string"""

    # NOTE: __len__ is enforced to return int at runtime (not even a subtype is allowed)
    @property
    def length(self) -> UInt64:
        """Returns the length of the instance"""

    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if the length is >0"""

    def __add__(self, other: Bytes | FixedBytes | bytes) -> Bytes:  # type: ignore[type-arg]
        """Concatenate with another Bytes, bytes, or FixedBytes"""

    def __radd__(self, other: bytes) -> Bytes:
        """Concatenate with another Bytes, bytes, or FixedBytes"""

    def __contains__(self, other: Bytes | FixedBytes | bytes) -> bool:  # type: ignore[type-arg]
        """Test whether another Bytes, bytes, or FixedBytes is a substring of this one.
        Note this is expensive due to a lack of AVM support."""

    # ~
    def __invert__(self) -> typing.Self:
        """Can be bitwise inverted"""

    def __getitem__(
        self, index: UInt64 | int | slice[int | UInt64 | None, int | UInt64 | None, None]
    ) -> Bytes:  # maps to substring/substring3 if slice, extract/extract3 otherwise?
        """Returns a Bytes containing a single byte if indexed with UInt64 or int
        otherwise the substring of Bytes described by the slice"""

    def __iter__(self) -> Iterator[Bytes]:
        """Can be iterated, yielding each consecutive byte"""

    def __reversed__(self) -> Iterator[Bytes]:
        """Can be iterated in reverse, yield each preceding byte starting at the end"""

    # mypy suggests due to Liskov below should be other: object
    # need to consider ramifications here, ignoring it for now
    def __eq__(self, other: Bytes | FixedBytes | bytes) -> bool:  # type: ignore[override,type-arg]
        """Compare with with another Bytes, bytes, or FixedBytes using the `==` operator"""

    def __ne__(self, other: Bytes | FixedBytes | bytes) -> bool:  # type: ignore[override,type-arg]
        """Compare with with another Bytes, bytes, or FixedBytes using the `!=` operator"""

class Bytes(_BytesBase):
    """A byte sequence, with a maximum length of 4096 bytes, one of the primary data types on the AVM"""

    __match_value__: bytes
    __match_args__ = ("__match_value__",)

    def __init__(self, value: bytes = b"", /):
        """Bytes can be initialized with a Python bytes literal, or bytes variable
        declared at the module level"""

    def __iadd__(self, other: _BytesBase | bytes) -> typing.Self:
        """Concatenate Bytes with another Bytes, bytes, or FixedBytes
        e.g. `a += Bytes(b"World")`."""

    # bitwise operators
    # &
    def __and__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise and with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") & b"0F")`"""

    def __rand__(self, other: bytes) -> typing.Self:
        """Bytes can bitwise and with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") & b"0F")`"""

    def __iand__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise and with another Bytes, bytes, or FixedBytes e.g. `a &= Bytes(b"0F")`"""

    # ^
    def __xor__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise xor with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") ^ b"0F")`"""

    def __rxor__(self, other: bytes) -> typing.Self:
        """Bytes can bitwise xor with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") ^ b"0F")`"""

    def __ixor__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise xor with another Bytes, bytes, or FixedBytes e.g. `a ^= Bytes(b"0F")`"""
    # |
    def __or__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise or with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") | b"0F")`"""

    def __ror__(self, other: bytes) -> typing.Self:
        """Bytes can bitwise or with another Bytes, bytes, or FixedBytes e.g. `Bytes(b"FF") | b"0F")`"""

    def __ior__(self, other: typing.Self | FixedBytes | bytes) -> typing.Self:  # type: ignore[type-arg]
        """Bytes can bitwise or with another Bytes, bytes, or FixedBytes e.g. `a |= Bytes(b"0F")`"""

class BytesBacked(typing.Protocol):
    """Represents a type that is a single bytes value"""

    @classmethod
    def from_bytes(cls, value: Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""

    @property
    def bytes(self) -> Bytes:
        """Get the underlying Bytes"""

_TBytesLength = typing.TypeVar("_TBytesLength", bound=int)

class FixedBytes(typing.Generic[_TBytesLength], BytesBacked, _BytesBase, _Validatable):
    """A statically-sized byte sequence, where the length is known at compile time.

    Example:
        FixedBytes[typing.Literal[32]]  # A 32-byte fixed-size bytes value
    """

    __match_value__: bytes
    __match_args__ = ("__match_value__",)

    def __init__(self, value: Bytes | bytes = ..., /):
        """FixedBytes can be initialized with a Python bytes literal, or bytes variable declared at the module level.
        The length must match the type parameter."""

    # bitwise operators
    # &
    @typing.overload
    def __and__(self, other: typing.Self) -> typing.Self:
        """FixedBytes can bitwise and with another FixedBytes of the same length e.g. `FixedBytes(b"FF") & FixedBytes(b"0F")`"""

    @typing.overload
    def __and__(self, other: Bytes | FixedBytes | bytes) -> Bytes:  # type: ignore[type-arg]
        """FixedBytes can bitwise and with another Bytes, bytes, or FixedBytes e.g. `FixedBytes(b"FF") & b"0F")`"""

    def __rand__(self, other: bytes) -> Bytes:
        """FixedBytes can bitwise and with another Bytes, bytes, or FixedBytes e.g. `FixedBytes(b"FF") & b"0F")`"""

    def __iand__(self, other: Bytes | typing.Self | bytes) -> typing.Self:  # type: ignore[misc]
        """FixedBytes can bitwise and with another Bytes, bytes, or FixedBytes of the same length e.g. `a &= FixedBytes(b"0F")`"""

    # ^
    @typing.overload
    def __xor__(self, other: typing.Self) -> typing.Self:
        """FixedBytes can bitwise xor with another FixedBytes of the same length e.g. `FixedBytes(b"FF") ^ FixedBytes(b"0F")`"""

    @typing.overload
    def __xor__(self, other: Bytes | FixedBytes | bytes) -> Bytes:  # type: ignore[type-arg]
        """FixedBytes can bitwise xor with another Bytes, bytes, or FixedBytes e.g. `FixedBytes(b"FF") ^ b"0F")`"""

    def __rxor__(self, other: bytes) -> Bytes:
        """FixedBytes can bitwise xor with another FixedBytes, Bytes or bytes e.g. `FixedBytes(b"FF") ^ b"0F")`"""

    def __ixor__(self, other: Bytes | typing.Self | bytes) -> typing.Self:  # type: ignore[misc]
        """FixedBytes can bitwise xor with another Bytes, bytes, or FixedBytes of the same length e.g. `a ^= FixedBytes(b"0F")`"""

    # |
    @typing.overload
    def __or__(self, other: typing.Self) -> typing.Self:
        """FixedBytes can bitwise or with another FixedBytes of the same length e.g. `FixedBytes(b"FF") | FixedBytes(b"0F")`"""

    @typing.overload
    def __or__(self, other: Bytes | FixedBytes | bytes) -> Bytes:  # type: ignore[type-arg]
        """FixedBytes can bitwise or with another Bytes, bytes, or FixedBytes e.g. `FixedBytes(b"FF") | b"0F")`"""

    def __ror__(self, other: bytes) -> Bytes:
        """FixedBytes can bitwise or with another Bytes, bytes, or FixedBytes e.g. `FixedBytes(b"FF") | b"0F")`"""

    def __ior__(self, other: Bytes | typing.Self | bytes) -> typing.Self:  # type: ignore[misc]
        """FixedBytes can bitwise or with another Bytes, bytes, or FixedBytes of the same length e.g. `a |= FixedBytes(b"0F")`"""

class String(BytesBacked, Container[String]):
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

    # mypy suggests due to Liskov below should be other: object
    # need to consider ramifications here, ignoring it for now
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

class BigUInt(BytesBacked):
    """A variable length (max 512-bit) unsigned integer"""

    __match_value__: int
    __match_args__ = ("__match_value__",)

    # TODO: consider how to handle cases where sizes exceeds 512, which can happen on + or *,
    #       but the result is no longer usable with any further ops.
    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    def __init__(self, value: UInt64 | int = 0, /) -> None:
        """A BigUInt can be initialized with a UInt64, a Python int literal, or an int variable
        declared at the module level"""

    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
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

    # truthiness
    def __bool__(self) -> bool:
        """A BigUInt will evaluate to `False` if zero, and `True` otherwise"""

    # ~~~ https://docs.python.org/3/reference/datamodel.html#emulating-numeric-types ~~~
    # +
    def __add__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be added with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`."""

    def __radd__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be added with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`."""

    def __iadd__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be incremented with another BigUInt, UInt64 or int e.g. `a += BigUInt(2)`."""

    # -
    def __sub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `BigUInt(4) - 2`.

        This will error on underflow"""

    def __rsub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `4 - BigUInt(2)`.

        This will error on underflow"""

    def __isub__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `a -= BigUInt(2)`.

        This will error on underflow"""

    # *
    def __mul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`."""

    def __rmul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`."""

    def __imul__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `a*= BigUInt(2)`."""

    # //
    def __floordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `BigUInt(4) // 2`.

        This will error on divide by zero"""

    def __rfloordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `4 // BigUInt(2)`.

        This will error on divide by zero"""

    def __ifloordiv__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `a //= BigUInt(2)`.

        This will error on divide by zero"""

    # %
    def __mod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `BigUInt(4) % 2`.

        This will error on mod by zero"""

    def __rmod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `4 % BigUInt(2)`.

        This will error on mod by zero"""

    def __imod__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `a %= BigUInt(2)`.

        This will error on mod by zero"""

    # &
    def __and__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `BigUInt(4) & 2`"""

    def __rand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `4 & BigUInt(2)`"""

    def __iand__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `a &= BigUInt(2)`"""

    # ^
    def __xor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `BigUInt(4) ^ 2`"""

    def __rxor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `4 ^ BigUInt(2)`"""

    def __ixor__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `a ^= BigUInt(2)`"""

    # |
    def __or__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `BigUInt(4) | 2`"""

    def __ror__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `4 | BigUInt(2)`"""

    def __ior__(self, other: BigUInt | UInt64 | int) -> BigUInt:
        """A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `a |= BigUInt(2)`"""

    def __pos__(self) -> BigUInt:
        """Supports unary + operator. Redundant given the type is unsigned"""
