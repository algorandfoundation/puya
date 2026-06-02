import typing

from algopy import (
    Account,
    Array,
    BaseContract,
    BigUInt,
    Bytes,
    FixedBytes,
    ImmutableArray,
    String,
    Struct,
    Txn,
    UInt64,
    arc4,
    op,
    subroutine,
)


class MyStruct(arc4.Struct):
    x: arc4.UInt64
    y: arc4.UInt8


class NativeStruct(Struct):
    a: UInt64
    b: UInt64


class BytesBackedOpsContract(BaseContract):
    def approval_program(self) -> bool:
        test_hash_ops()
        test_byte_manipulation_ops()
        test_conversion_ops()
        test_bitwise_ops()
        test_bytes_backed_state_keys()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_hash_ops() -> None:
    fb = FixedBytes[typing.Literal[4]](b"test")
    s = String("test")
    acct = Account(op.Txn.sender.bytes)
    big = BigUInt(42)

    # sha256 of various types
    assert op.sha256(fb)
    assert op.sha256(s)
    assert op.sha256(acct)
    assert op.sha256(big)
    assert op.sha256(arc4.UInt64(42))
    assert op.sha256(arc4.Byte(255))
    assert op.sha256(arc4.UInt16(1000))
    assert op.sha256(arc4.UInt32(100000))
    assert op.sha256(arc4.UInt128(999999))
    assert op.sha256(arc4.String("test"))
    assert op.sha256(arc4.Bool(True))
    assert op.sha256(arc4.Address(op.Txn.sender))
    assert op.sha256(arc4.DynamicBytes(b"\x00\x02hi"))
    assert op.sha256(arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]("1.0"))
    assert op.sha256(arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("1.0"))
    assert op.sha256(arc4.StaticArray(arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3)))
    assert op.sha256(arc4.DynamicArray[arc4.UInt8](arc4.UInt8(1), arc4.UInt8(2)))
    assert op.sha256(arc4.Tuple((arc4.UInt8(1), arc4.String("hello"))))
    assert op.sha256(MyStruct(x=arc4.UInt64(42), y=arc4.UInt8(7)))
    assert op.sha256(ImmutableArray((UInt64(1), UInt64(2), UInt64(3))))
    assert op.sha256(Array((UInt64(10), UInt64(20))))
    assert op.sha256(NativeStruct(a=UInt64(1), b=UInt64(2)))

    # keccak256
    assert op.keccak256(fb)
    assert op.keccak256(acct)
    assert op.keccak256(arc4.UInt32(100))
    assert op.keccak256(arc4.DynamicArray[arc4.UInt8](arc4.UInt8(1), arc4.UInt8(2)))
    assert op.keccak256(NativeStruct(a=UInt64(1), b=UInt64(2)))

    # sha512_256
    assert op.sha512_256(fb)
    assert op.sha512_256(arc4.String("test"))
    assert op.sha512_256(arc4.UInt64(42))
    assert op.sha512_256(ImmutableArray((UInt64(1), UInt64(2))))

    # sha3_256
    assert op.sha3_256(fb)
    assert op.sha3_256(s)
    assert op.sha3_256(big)
    assert op.sha3_256(arc4.StaticArray(arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3)))
    assert op.sha3_256(Array((UInt64(10), UInt64(20))))


@subroutine
def test_byte_manipulation_ops() -> None:
    fb = FixedBytes[typing.Literal[5]](b"hello")
    s = String("hello")
    acct = Account(op.Txn.sender.bytes)

    # concat mixing different BytesBacked types
    result = op.concat(fb, s)
    assert result.length == UInt64(10)

    assert op.concat(arc4.String("hello"), acct)
    assert op.concat(acct, s)
    assert op.concat(BigUInt(1000), BigUInt(1000))
    assert op.concat(arc4.DynamicBytes(b"\x00\x02hi"), fb)
    assert op.concat(arc4.UInt64(42), arc4.UInt64(43))
    assert op.concat(Array((UInt64(10), UInt64(20))), fb)
    assert op.concat(ImmutableArray((UInt64(1),)), NativeStruct(a=UInt64(1), b=UInt64(2)))

    # extract of various types
    assert op.extract(s, 1, 3) == b"ell"
    assert op.extract(acct, 0, 4)
    assert op.extract(arc4.String("hello"), 0, 2)

    # substring
    assert op.substring(fb, 1, 4) == b"ell"
    assert op.substring(arc4.UInt64(42), 0, 4)

    # getbyte
    assert op.getbyte(arc4.UInt64(42), 7) == 42
    assert op.getbyte(BigUInt(1000), 0) >= UInt64(0)
    assert op.getbyte(s, 0) == 104  # 'h'

    # setbyte
    modified = op.setbyte(fb, 0, 72)
    assert modified == b"Hello"

    # replace
    replaced = op.replace(BigUInt(256), 0, Bytes(b"\x00"))
    assert replaced

    replaced2 = op.replace(acct, 0, Bytes(b"\x00"))
    assert replaced2

    # extract_uint16/32/64
    fb8 = FixedBytes[typing.Literal[8]](b"\x00\x00\x00\x00\x00\x00\x00\x2a")
    assert op.extract_uint64(fb8, 0) == 42
    assert op.extract_uint16(arc4.UInt32(1000), 0) >= UInt64(0)
    assert op.extract_uint32(arc4.UInt32(1000), 0) >= UInt64(0)


@subroutine
def test_conversion_ops() -> None:
    # btoi of various types
    fb = FixedBytes[typing.Literal[8]](b"\x00\x00\x00\x00\x00\x00\x00\x2a")
    assert op.btoi(fb) == 42
    assert op.btoi(arc4.UInt64(100)) == 100
    assert op.btoi(Bytes(b"\x2a")) == 42

    # base64_decode
    encoded = Bytes(b"aGVsbG8=")
    decoded = op.base64_decode(op.Base64.StdEncoding, encoded)
    assert decoded == b"hello"


@subroutine
def test_bitwise_ops() -> None:
    fb = FixedBytes[typing.Literal[4]](b"test")
    s = String("test")
    acct = Account(op.Txn.sender.bytes)

    # bitlen of various types
    assert op.bitlen(fb) > UInt64(0)
    assert op.bitlen(s) > UInt64(0)
    assert op.bitlen(acct) > UInt64(0)
    assert op.bitlen(BigUInt(1000)) > UInt64(0)
    assert op.bitlen(arc4.UInt64(42)) > UInt64(0)
    assert op.bitlen(arc4.String("hello")) > UInt64(0)
    assert op.bitlen(arc4.DynamicBytes(b"\x00\x02hi")) > UInt64(0)
    assert op.bitlen(arc4.Tuple((arc4.UInt8(1), arc4.String("hello")))) > UInt64(0)
    assert op.bitlen(MyStruct(x=arc4.UInt64(42), y=arc4.UInt8(7))) > UInt64(0)
    assert op.bitlen(ImmutableArray((UInt64(1), UInt64(2), UInt64(3)))) > UInt64(0)
    assert op.bitlen(NativeStruct(a=UInt64(1), b=UInt64(2))) > UInt64(0)

    # getbit / setbit_bytes with String
    bit = op.getbit(s, 0)
    result = op.setbit_bytes(s, 0, not bit)
    assert result != s.bytes

    # getbit / setbit_bytes with FixedBytes
    bit2 = op.getbit(fb, 0)
    result2 = op.setbit_bytes(fb, 0, not bit2)
    assert result2 != fb.bytes

    # getbit / setbit_bytes with arc4.Bool
    arc4_bool = arc4.Bool(True)
    toggled = op.setbit_bytes(arc4_bool, 0, False)
    assert toggled != arc4_bool.bytes

    # getbit with Account
    assert op.getbit(acct, 0) >= UInt64(0)

    # getbit with arc4.UInt64
    assert op.getbit(arc4.UInt64(42), 63) >= UInt64(0)


@subroutine
def test_bytes_backed_state_keys() -> None:
    fb = FixedBytes[typing.Literal[4]](b"test")

    op.AppGlobal.delete(fb)
    op.AppLocal.delete(Txn.sender, fb)
    op.Box.delete(fb)
