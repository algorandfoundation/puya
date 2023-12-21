import typing

from puyapy import Contract, arc4, log, subroutine

Decimal: typing.TypeAlias = arc4.UFixedNxM[typing.Literal[64], typing.Literal[9]]


class Vector(arc4.Struct):
    x: Decimal
    y: Decimal


class Flags(arc4.Struct):
    a: arc4.Bool
    b: arc4.Bool
    c: arc4.Bool
    d: arc4.Bool


class VectorFlags(arc4.Struct):
    vector: Vector
    flags: Flags


class Arc4StructsTypeContract(Contract):
    def approval_program(self) -> bool:
        coord_1 = Vector(x=Decimal("35.382882839"), y=Decimal("150.382884930"))
        coord_2 = Vector(x=Decimal("35.382882839"), y=Decimal("150.382884930"))
        coord_3 = add(coord_1, coord_2)
        for val in (coord_3.x, coord_3.y):
            log(val.bytes)

        flags = Flags(a=arc4.Bool(True), b=arc4.Bool(False), c=arc4.Bool(True), d=arc4.Bool(False))
        check(flags)
        log(flags.bytes)

        nested_decode(VectorFlags(coord_1, flags))

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def add(v1: Vector, v2: Vector) -> Vector:
    return Vector(
        x=Decimal.encode(v1.x.decode() + v2.x.decode()),
        y=Decimal.encode(v1.y.decode() + v2.y.decode()),
    )


@subroutine
def check(flags: Flags) -> None:
    assert flags.a.decode()
    assert not flags.b.decode()
    assert flags.c.decode()
    assert not flags.d.decode()


@subroutine
def nested_decode(vector_flags: VectorFlags) -> None:
    assert vector_flags.vector.x.decode() == 35382882839
    assert vector_flags.flags.c.decode()
