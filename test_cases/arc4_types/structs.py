import typing

from algopy import Contract, arc4, log, op, subroutine

Decimal: typing.TypeAlias = arc4.UFixedNxM[typing.Literal[64], typing.Literal[9]]


class Vector(arc4.Struct, kw_only=True):
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


class FrozenButMutable(arc4.Struct, frozen=True):
    mutable: arc4.DynamicBytes


class FrozenAndImmutable(arc4.Struct, frozen=True):
    one: arc4.UInt64
    two: arc4.UInt64


class Arc4StructsTypeContract(Contract):
    def approval_program(self) -> bool:
        coord_1 = Vector(x=Decimal("35.382882839"), y=Decimal("150.382884930"))
        coord_2 = Vector(y=Decimal("150.382884930"), x=Decimal("35.382882839"))
        coord_3 = add(coord_1.copy(), coord_2.copy())
        for val in (coord_3.x, coord_3.y):
            log(val.bytes)

        flags = Flags(a=arc4.Bool(True), b=arc4.Bool(False), c=arc4.Bool(True), d=arc4.Bool(False))
        check(flags.copy())
        log(flags.bytes)
        assert Vector.from_bytes(coord_1.bytes).bytes == coord_1.bytes

        nested_decode(VectorFlags(coord_1.copy(), flags.copy()))

        mutable = FrozenButMutable(arc4.DynamicBytes())
        copy = mutable.copy()
        copy.mutable.append(arc4.Byte(42))
        assert mutable != copy, "expected copy is different"

        immutable = FrozenAndImmutable(arc4.UInt64(12), arc4.UInt64(34))
        no_copy = immutable
        assert no_copy == immutable

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def add(v1: Vector, v2: Vector) -> Vector:
    return Vector(
        x=add_decimal(v1.x, v2.x),
        y=add_decimal(v1.y, v2.y),
    )


@subroutine
def check(flags: Flags) -> None:
    assert flags.a.native
    assert not flags.b.native
    assert flags.c.native
    assert not flags.d.native


@subroutine
def nested_decode(vector_flags: VectorFlags) -> None:
    assert vector_flags.vector.x.bytes == op.itob(35382882839)
    assert vector_flags.flags.c.native


@subroutine
def add_decimal(x: Decimal, y: Decimal) -> Decimal:
    return Decimal.from_bytes(op.itob(op.btoi(x.bytes) + op.btoi(y.bytes)))
