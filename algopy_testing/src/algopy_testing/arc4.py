from __future__ import annotations

import decimal
import types
import typing

import algopy_testing.primitives as algopy
from algopy_testing.constants import ARC4_RETURN_PREFIX, BITS_IN_BYTE, UINT64_SIZE, UINT512_SIZE
from algopy_testing.utils import as_bytes, as_int, as_int64, as_int512, as_string, int_to_bytes

if typing.TYPE_CHECKING:
    from collections.abc import Callable

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def abimethod(
    fn: Callable[_P, _R],
) -> Callable[_P, _R]:
    return fn


class ARC4Contract:
    pass


class String:
    pass


_TBitSize = typing.TypeVar("_TBitSize", bound=int)
_RETURN_PREFIX = algopy.Bytes(ARC4_RETURN_PREFIX)


class _ABIEncoded(typing.Protocol):
    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
        ...

    @property
    def bytes(self) -> algopy.Bytes:
        """Get the underlying Bytes"""
        ...

    @classmethod
    def from_log(cls, log: algopy.Bytes, /) -> typing.Self:
        """Load an ABI type from application logs,
        checking for the ABI return prefix `0x151f7c75`"""
        ...


# https://stackoverflow.com/a/75395800
class _UIntNMeta(type(_ABIEncoded), typing.Generic[_TBitSize]):  # type: ignore  # noqa: PGH003
    __concrete__: dict[type[_TBitSize], type] = {}  # noqa: RUF012

    def __getitem__(cls, key_t: type[_TBitSize]) -> type:
        cache = cls.__concrete__
        if c := cache.get(key_t, None):
            return c
        cache[key_t] = c = types.new_class(
            f"{cls.__name__}[{key_t.__name__}]", (cls,), {}, lambda ns: ns.update(_t=key_t)
        )
        return c


class _UIntN(_ABIEncoded, typing.Generic[_TBitSize], metaclass=_UIntNMeta):
    _t: type[_TBitSize]
    _bit_size: int
    _max_bits_len: int
    _max_bytes_len: int
    _max_int: int
    _value: bytes  # underlying 'bytes' value representing the UIntN

    def __init__(self, value: algopy.BigUInt | algopy.UInt64 | int = 0, /) -> None:
        self._bit_size = as_int(typing.get_args(self._t)[0], max=self._max_bits_len)
        self._max_int = 2**self._bit_size - 1
        self._max_bytes_len = self._bit_size // BITS_IN_BYTE

        value = as_int(value, max=self._max_int)
        bytes_value = int_to_bytes(value, self._max_bytes_len)
        self._value = as_bytes(bytes_value, max_size=self._max_bytes_len)

    # ~~~ https://docs.python.org/3/reference/datamodel.html#basic-customization ~~~
    # TODO: mypy suggests due to Liskov below should be other: object
    #       need to consider ramifications here, ignoring it for now
    def __eq__(  # type: ignore[override]
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __ne__(  # type: ignore[override]
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __le__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __lt__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __ge__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __gt__(
        self,
        other: UIntN[_TBitSize] | BigUIntN[_TBitSize] | algopy.UInt64 | algopy.BigUInt | int,
    ) -> bool:
        raise NotImplementedError

    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
        value = as_bytes(value)
        result = cls()
        result._value = value  # noqa: SLF001
        return result

    @property
    def bytes(self) -> algopy.Bytes:
        """Get the underlying Bytes"""
        return algopy.Bytes(self._value)

    @classmethod
    def from_log(cls, log: algopy.Bytes, /) -> typing.Self:
        """Load an ABI type from application logs,
        checking for the ABI return prefix `0x151f7c75`"""
        if log[:4] == _RETURN_PREFIX:
            return cls.from_bytes(log[4:])
        raise ValueError("ABI return prefix not found")


class UIntN(_UIntN[_TBitSize], typing.Generic[_TBitSize]):
    """An ARC4 UInt consisting of the number of bits specified.

    Max Size: 64 bits"""

    _max_bits_len = UINT64_SIZE

    @property
    def native(self) -> algopy.UInt64:
        """Return the UInt64 representation of the value after ARC4 decoding"""
        return algopy.UInt64(int.from_bytes(self._value))

    def __eq__(self, other: object) -> bool:
        return as_int64(self.native) == as_int(other, max=None)

    def __ne__(self, other: object) -> bool:
        return as_int64(self.native) != as_int(other, max=None)

    def __le__(self, other: object) -> bool:
        return as_int64(self.native) <= as_int(other, max=None)

    def __lt__(self, other: object) -> bool:
        return as_int64(self.native) < as_int(other, max=None)

    def __ge__(self, other: object) -> bool:
        return as_int64(self.native) >= as_int(other, max=None)

    def __gt__(self, other: object) -> bool:
        return as_int64(self.native) > as_int(other, max=None)

    def __bool__(self) -> bool:
        return bool(self.native)


class BigUIntN(_UIntN[_TBitSize], typing.Generic[_TBitSize]):
    """An ARC4 UInt consisting of the number of bits specified.

    Max size: 512 bits"""

    _max_bits_len = UINT512_SIZE

    @property
    def native(self) -> algopy.BigUInt:
        """Return the UInt64 representation of the value after ARC4 decoding"""
        return algopy.BigUInt.from_bytes(self._value)

    def __eq__(self, other: object) -> bool:
        return as_int512(self.native) == as_int(other, max=None)

    def __ne__(self, other: object) -> bool:
        return as_int512(self.native) != as_int(other, max=None)

    def __le__(self, other: object) -> bool:
        return as_int512(self.native) <= as_int(other, max=None)

    def __lt__(self, other: object) -> bool:
        return as_int512(self.native) < as_int(other, max=None)

    def __ge__(self, other: object) -> bool:
        return as_int512(self.native) >= as_int(other, max=None)

    def __gt__(self, other: object) -> bool:
        return as_int512(self.native) > as_int(other, max=None)

    def __bool__(self) -> bool:
        return bool(self.native)


_TDecimalPlaces = typing.TypeVar("_TDecimalPlaces", bound=int)
_MAX_M_SIZE = 160


class _UFixedNxMMeta(type(_ABIEncoded), typing.Generic[_TBitSize, _TDecimalPlaces]):  # type: ignore  # noqa: PGH003
    __concrete__: dict[tuple[type[_TBitSize], type[_TDecimalPlaces]], type] = {}  # noqa: RUF012

    def __getitem__(cls, key_t: tuple[type[_TBitSize], type[_TDecimalPlaces]]) -> type:
        cache = cls.__concrete__
        if c := cache.get(key_t, None):
            return c

        size_t, decimal_t = key_t
        cache[key_t] = c = types.new_class(
            f"{cls.__name__}[{size_t.__name__}, {decimal_t.__name__}]",
            (cls,),
            {},
            lambda ns: ns.update(_size_t=size_t, _decimal_t=decimal_t),
        )
        return c


class _UFixedNxM(
    _ABIEncoded, typing.Generic[_TBitSize, _TDecimalPlaces], metaclass=_UFixedNxMMeta
):
    _size_t: type[_TBitSize]
    _decimal_t: type[_TDecimalPlaces]
    _n: int
    _m: int
    _max_bits_len: int
    _max_bytes_len: int
    _value: bytes  # underlying 'bytes' value representing the UFixedNxM

    def __init__(self, value: str = "0.0", /):
        """
        Construct an instance of UFixedNxM where value (v) is determined from the original
        decimal value (d) by the formula v = round(d * (10^M))
        """
        self._n = as_int(typing.get_args(self._size_t)[0], max=self._max_bits_len)
        self._m = as_int(typing.get_args(self._decimal_t)[0], max=_MAX_M_SIZE)
        self._max_int = 2**self._n - 1
        self._max_bytes_len = self._n // BITS_IN_BYTE

        value = as_string(value)
        with decimal.localcontext(
            decimal.Context(
                prec=160,
                traps=[
                    decimal.Rounded,
                    decimal.InvalidOperation,
                    decimal.Overflow,
                    decimal.DivisionByZero,
                ],
            )
        ):
            try:
                d = decimal.Decimal(value)
            except ArithmeticError as ex:
                raise ValueError(f"Invalid decimal literal: {value}") from ex
            if d < 0:
                raise ValueError("Negative numbers not allowed")
            try:
                q = d.quantize(decimal.Decimal(f"1e-{self._m}"))
            except ArithmeticError as ex:
                raise ValueError(f"Too many decimals, expected max of {self._m}") from ex

            int_value = round(q * (10**self._m))
            int_value = as_int(int_value, max=self._max_int)
            bytes_value = int_to_bytes(int_value, self._max_bytes_len)
            self._value = as_bytes(bytes_value, max_size=self._max_bytes_len)

    def __bool__(self) -> bool:
        """Returns `True` if not equal to zero"""
        return bool(int.from_bytes(self._value))

    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""
        value = as_bytes(value)
        result = cls()
        result._value = value  # noqa: SLF001
        return result

    @property
    def bytes(self) -> algopy.Bytes:
        """Get the underlying Bytes"""
        return algopy.Bytes(self._value)

    @classmethod
    def from_log(cls, log: algopy.Bytes, /) -> typing.Self:
        """Load an ABI type from application logs,
        checking for the ABI return prefix `0x151f7c75`"""
        if log[:4] == _RETURN_PREFIX:
            return cls.from_bytes(log[4:])
        raise ValueError("ABI return prefix not found")


class UFixedNxM(
    _UFixedNxM[_TBitSize, _TDecimalPlaces], typing.Generic[_TBitSize, _TDecimalPlaces]
):
    """An ARC4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 64 bits"""

    _max_bits_len: int = UINT64_SIZE


class BigUFixedNxM(
    _UFixedNxM[_TBitSize, _TDecimalPlaces], typing.Generic[_TBitSize, _TDecimalPlaces]
):
    """An ARC4 UFixed representing a decimal with the number of bits and precision specified.

    Max size: 512 bits"""

    _max_bits_len: int = UINT512_SIZE


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
