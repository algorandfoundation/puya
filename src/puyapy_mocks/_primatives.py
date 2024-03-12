from __future__ import annotations


# TODO: Need to perform underflow and overflow checks
class UInt64:
    __match_value__: int
    __match_args__ = ("__match_value__",)

    def __init__(self, value: int, /) -> None:
        self.__match_value__ = value

    def __eq__(self, other: UInt64 | int) -> bool:  # type: ignore[override]
        if isinstance(other, UInt64):
            return self.__match_value__ == other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ == other
        else:
            return NotImplemented

    def __ne__(self, other: UInt64 | int) -> bool:  # type: ignore[override]
        if isinstance(other, UInt64):
            return self.__match_value__ != other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ != other
        else:
            return NotImplemented

    def __le__(self, other: UInt64 | int) -> bool:
        if isinstance(other, UInt64):
            return self.__match_value__ <= other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ <= other
        else:
            return NotImplemented

    def __lt__(self, other: UInt64 | int) -> bool:
        if isinstance(other, UInt64):
            return self.__match_value__ < other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ < other
        else:
            return NotImplemented

    def __ge__(self, other: UInt64 | int) -> bool:
        if isinstance(other, UInt64):
            return self.__match_value__ >= other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ >= other
        else:
            return NotImplemented

    def __gt__(self, other: UInt64 | int) -> bool:
        if isinstance(other, UInt64):
            return self.__match_value__ > other.__match_value__
        elif isinstance(other, int):
            return self.__match_value__ > other
        else:
            return NotImplemented

    def __bool__(self) -> bool:
        return self.__match_value__ != 0

    def __add__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ + other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ + other)
        else:
            return NotImplemented

    def __radd__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other + self.__match_value__)
        else:
            return NotImplemented

    def __iadd__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ += other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ += other
        else:
            return NotImplemented
        return self

    def __sub__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ - other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ - other)
        else:
            return NotImplemented

    def __rsub__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other - self.__match_value__)
        else:
            return NotImplemented

    def __isub__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ -= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ -= other
        else:
            return NotImplemented
        return self

    def __mul__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ * other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ * other)
        else:
            return NotImplemented

    def __rmul__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other * self.__match_value__)
        else:
            return NotImplemented

    def __imul__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ *= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ *= other
        else:
            return NotImplemented
        return self

    def __floordiv__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ // other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ // other)
        else:
            return NotImplemented

    def __rfloordiv__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other // self.__match_value__)
        else:
            return NotImplemented

    def __ifloordiv__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ //= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ //= other
        else:
            return NotImplemented
        return self

    def __mod__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ % other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ % other)
        else:
            return NotImplemented

    def __rmod__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other % self.__match_value__)
        else:
            return NotImplemented

    def __imod__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ %= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ %= other
        else:
            return NotImplemented
        return self

    def __pow__(self, power: UInt64 | int) -> UInt64:
        if isinstance(power, UInt64):
            return UInt64(self.__match_value__**power.__match_value__)
        elif isinstance(power, int):
            return UInt64(self.__match_value__**power)
        else:
            return NotImplemented

    def __rpow__(self, power: UInt64 | int) -> UInt64:
        if isinstance(power, int):
            return UInt64(power**self.__match_value__)
        else:
            return NotImplemented

    def __ipow__(self, power: UInt64 | int) -> UInt64:  # noqa: PYI034, PYI034
        if isinstance(power, UInt64):
            self.__match_value__ **= power.__match_value__
        elif isinstance(power, int):
            self.__match_value__ **= power
        else:
            return NotImplemented
        return self

    def __lshift__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ << other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ << other)
        else:
            return NotImplemented

    def __rlshift__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other << self.__match_value__)
        else:
            return NotImplemented

    def __ilshift__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ <<= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ <<= other
        else:
            return NotImplemented
        return self

    def __rshift__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ >> other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ >> other)
        else:
            return NotImplemented

    def __rrshift__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other >> self.__match_value__)
        else:
            return NotImplemented

    def __irshift__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ >>= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ >>= other
        else:
            return NotImplemented
        return self

    def __and__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ & other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ & other)
        else:
            return NotImplemented

    def __rand__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other & self.__match_value__)
        else:
            return NotImplemented

    def __iand__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ &= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ &= other
        else:
            return NotImplemented
        return self

    def __xor__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ ^ other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ ^ other)
        else:
            return NotImplemented

    def __rxor__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other ^ self.__match_value__)
        else:
            return NotImplemented

    def __ixor__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ ^= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ ^= other
        else:
            return NotImplemented
        return self

    def __or__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, UInt64):
            return UInt64(self.__match_value__ | other.__match_value__)
        elif isinstance(other, int):
            return UInt64(self.__match_value__ | other)
        else:
            return NotImplemented

    def __ror__(self, other: UInt64 | int) -> UInt64:
        if isinstance(other, int):
            return UInt64(other | self.__match_value__)
        else:
            return NotImplemented

    def __ior__(self, other: UInt64 | int) -> UInt64:  # noqa: PYI034
        if isinstance(other, UInt64):
            self.__match_value__ |= other.__match_value__
        elif isinstance(other, int):
            self.__match_value__ |= other
        else:
            return NotImplemented
        return self

    def __invert__(self) -> UInt64:
        return UInt64(~self.__match_value__)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"{self.__match_value__}"

    def __int__(self) -> int:
        return self.__match_value__

    def __index__(self) -> int:
        return self.__match_value__

    def __bytes__(self) -> bytes:
        return int.to_bytes(self.__match_value__, 8)


class Bytes:
    __match_value__: bytes
    __match_args__ = ("__match_value__",)

    def __init__(self, value: bytes = b"", /) -> None:
        self.__match_value__ = value

    def __bytes__(self) -> bytes:
        return self.__match_value__

    @property
    def length(self) -> UInt64:
        return UInt64(len(self.__match_value__))

    def __getitem__(self, index: UInt64 | int | slice) -> Bytes:
        if isinstance(index, (UInt64, int)):
            i = int(index)
            return Bytes(self.__match_value__[i : i + 1])
        elif isinstance(index, slice):
            return Bytes(self.__match_value__[index.start : index.stop : index.step])
        else:
            return NotImplemented

    def __add__(self, other: Bytes | bytes) -> Bytes:
        if isinstance(other, bytes):
            other = Bytes(other)
        return Bytes(self.__match_value__ + bytes(other))

    def __eq__(self, other: Bytes | bytes) -> bool:  # type: ignore[override]
        return self.__match_value__ == bytes(other)

    def __int__(self) -> int:
        return int.from_bytes(self.__match_value__)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return self.__match_value__.decode()


def convert_to_bytes(arg: UInt64 | int | Bytes | bytes | str) -> bytes:
    if isinstance(arg, (UInt64, int)):
        return int.to_bytes(int(arg), 8)
    elif isinstance(arg, Bytes):
        return bytes(arg)
    elif isinstance(arg, bytes):
        return arg
    elif isinstance(arg, str):
        return arg.encode()

    return NotImplemented
