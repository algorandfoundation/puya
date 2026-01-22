import typing

from algopy import (
    Account,
    Application,
    Asset,
    BigUInt,
    Bytes,
    Contract,
    String,
    Struct,
    UInt64,
    arc4,
    subroutine,
)


class NativeStruct(Struct):
    a: UInt64
    b: bool


class Arc4Struct(arc4.Struct):
    x: arc4.UInt64
    y: arc4.String


class MyNamedTuple(typing.NamedTuple):
    x: UInt64
    y: String


class Arc4EncodeDecodeContract(Contract):
    def approval_program(self) -> bool:
        test_native_struct()
        test_arc4_struct()
        test_uint64()
        test_biguint()
        test_string()
        test_bytes()
        test_bool()
        test_account()
        test_asset()
        test_application()
        test_arc4_uint64()
        test_arc4_string()
        test_tuple()
        test_named_tuple()
        test_arc4_dynamic_array()
        test_arc4_static_array()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine()
def test_native_struct() -> None:
    original = NativeStruct(a=UInt64(1), b=True)
    encoded = arc4.encode(original)
    assert encoded == Bytes.from_hex("000000000000000180")
    decoded = arc4.decode(NativeStruct, encoded)
    assert decoded == original


@subroutine()
def test_arc4_struct() -> None:
    original = Arc4Struct(x=arc4.UInt64(42), y=arc4.String("hello"))
    encoded = arc4.encode(original)
    decoded = arc4.decode(Arc4Struct, encoded)
    assert decoded == original


@subroutine()
def test_uint64() -> None:
    value = UInt64(42)
    encoded = arc4.encode(value)
    # UInt64 encodes as 8-byte big-endian
    assert encoded == Bytes.from_hex("000000000000002A")
    decoded = arc4.decode(UInt64, encoded)
    assert decoded == value


@subroutine()
def test_biguint() -> None:
    value = BigUInt(42)
    encoded = arc4.encode(value)
    decoded = arc4.decode(BigUInt, encoded)
    assert decoded == value


@subroutine()
def test_string() -> None:
    value = String("hello")
    encoded = arc4.encode(value)
    # 16 bit len + UTF-8 string
    assert encoded == Bytes.from_hex("000568656C6C6F")
    decoded = arc4.decode(String, encoded)
    assert decoded == value


@subroutine()
def test_bytes() -> None:
    value = Bytes(b"\x01\x02\x03")
    encoded = arc4.encode(value)
    # 16 bit len + bytes
    assert encoded == Bytes.from_hex("0003010203")
    decoded = arc4.decode(Bytes, encoded)
    assert decoded == value


@subroutine()
def test_bool() -> None:
    encoded_true = arc4.encode(True)
    assert encoded_true == Bytes.from_hex("80")
    decoded_true = arc4.decode(bool, encoded_true)
    assert decoded_true

    encoded_false = arc4.encode(False)
    assert encoded_false == Bytes.from_hex("00")
    decoded_false = arc4.decode(bool, encoded_false)
    assert not decoded_false


@subroutine()
def test_account() -> None:
    value = Account("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ")
    encoded = arc4.encode(value)
    decoded = arc4.decode(Account, encoded)
    assert decoded == value


@subroutine()
def test_asset() -> None:
    value = Asset(42)
    encoded = arc4.encode(value)
    assert encoded == Bytes.from_hex("000000000000002A")
    decoded = arc4.decode(Asset, encoded)
    assert decoded == value


@subroutine()
def test_application() -> None:
    value = Application(123)
    encoded = arc4.encode(value)
    assert encoded == Bytes.from_hex("000000000000007B")
    decoded = arc4.decode(Application, encoded)
    assert decoded == value


@subroutine()
def test_arc4_uint64() -> None:
    value = arc4.UInt64(42)
    encoded = arc4.encode(value)
    assert encoded == Bytes.from_hex("000000000000002A")
    decoded = arc4.decode(arc4.UInt64, encoded)
    assert decoded == value


@subroutine()
def test_arc4_string() -> None:
    value = arc4.String("hello")
    encoded = arc4.encode(value)
    assert encoded == Bytes.from_hex("000568656C6C6F")
    decoded = arc4.decode(arc4.String, encoded)
    assert decoded == value


@subroutine()
def test_tuple() -> None:
    value = (UInt64(1), UInt64(2))
    encoded = arc4.encode(value)
    assert encoded == Bytes.from_hex("00000000000000010000000000000002")
    decoded = arc4.decode(tuple[UInt64, UInt64], encoded)
    assert decoded == value


@subroutine()
def test_named_tuple() -> None:
    value = MyNamedTuple(x=UInt64(5), y=String("test"))
    encoded = arc4.encode(value)
    decoded = arc4.decode(MyNamedTuple, encoded)
    assert decoded == value


@subroutine()
def test_arc4_dynamic_array() -> None:
    value = arc4.DynamicArray(arc4.UInt64(1), arc4.UInt64(2), arc4.UInt64(3))
    encoded = arc4.encode(value)
    decoded = arc4.decode(arc4.DynamicArray[arc4.UInt64], encoded)
    assert decoded == value


@subroutine()
def test_arc4_static_array() -> None:
    value = arc4.StaticArray(arc4.UInt64(10), arc4.UInt64(20))
    encoded = arc4.encode(value)
    decoded = arc4.decode(arc4.StaticArray[arc4.UInt64, typing.Literal[2]], encoded)
    assert decoded == value
