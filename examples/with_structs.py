from puyapy import Array, BigUInt, Bytes, Struct, UInt64, subroutine


class NamedUInt64(Struct):
    name: Bytes
    value: UInt64


class NamedBigUInt(Struct):
    name: Bytes
    value: BigUInt


class AllMyData(Struct):
    names: Array[Bytes]
    smalls: Array[NamedUInt64]
    bigs: Array[NamedBigUInt]
    array2d: Array[Array[UInt64]]


@subroutine
def transform(src: Array[NamedUInt64]) -> Array[NamedBigUInt]:
    dst = Array[NamedBigUInt]()
    for item in src:
        dst.append(NamedBigUInt(name=item.name, value=BigUInt(item.value)))
    return dst
