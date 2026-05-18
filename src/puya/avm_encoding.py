import struct
from collections.abc import Sequence

encode_uint8 = struct.Struct(">B").pack
encode_int8 = struct.Struct(">b").pack
encode_label = struct.Struct(">h").pack


def encode_varuint(value: int) -> bytes:
    bits = value & 0x7F
    value >>= 7
    result = b""
    while value:
        result += encode_uint8(0x80 | bits)
        bits = value & 0x7F
        value >>= 7
    return result + encode_uint8(bits)


def encode_bytes(value: bytes) -> bytes:
    return encode_varuint(len(value)) + value


def encode_varuint_array(values: Sequence[int]) -> bytes:
    return b"".join((encode_varuint(len(values)), *map(encode_varuint, values)))


def encode_label_array(values: Sequence[int]) -> bytes:
    # note: op spec describes a label array size as a varuint
    #       however actual algod go implementation is just a single byte
    #       additionally max number of labels is 255
    return b"".join((encode_uint8(len(values)), *map(encode_label, values)))


def encode_bytes_array(values: Sequence[bytes]) -> bytes:
    return b"".join(
        (
            encode_varuint(len(values)),
            *map(encode_bytes, values),
        ),
    )
