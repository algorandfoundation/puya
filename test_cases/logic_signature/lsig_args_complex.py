import typing

from algopy import BigUInt, Bytes, String, UInt64, arc4, logicsig, op


class SimpleStruct(arc4.Struct):
    x: arc4.UInt64
    y: arc4.UInt64


class NestedStruct(arc4.Struct):
    header: arc4.UInt8
    data: SimpleStruct


class SimpleNamedTuple(typing.NamedTuple):
    a: arc4.UInt8
    b: arc4.UInt64


class OverwriteStruct(arc4.Struct):
    value: arc4.UInt8
    dont_overwrite_me: arc4.Bool


@logicsig
def args_complex(
    arg0: UInt64,
    arg1: Bytes,
    arg2: BigUInt,
    arg3: String,
    arg4: bool,
    arg5: arc4.UInt8,
    arg6: arc4.UInt64,
    arg7: arc4.UInt128,
    arg8: arc4.Address,
    arg9: arc4.Bool,
    arg10: arc4.String,
    arg11: arc4.DynamicBytes,
    arg12: arc4.StaticArray[arc4.Byte, typing.Literal[4]],
    arg13: SimpleStruct,
    arg14: NestedStruct,
    arg15: arc4.Tuple[arc4.UInt8, arc4.UInt64],
    arg16: SimpleNamedTuple,
    arg17: tuple[UInt64, Bytes],
    arg18: tuple[UInt64, tuple[Bytes, UInt64]],
    arg19: OverwriteStruct,
    arg20: arc4.DynamicArray[arc4.UInt8],
) -> bool:
    # verify args match raw op.arg values
    assert arg0 == op.btoi(op.arg(0))
    assert arg1 == op.arg(1)
    assert arg2.bytes == op.arg(2)
    assert arg3.bytes == op.arg(3)
    assert arg4 == (op.btoi(op.arg(4)) != 0)
    assert arg5.bytes == op.arg(5)
    assert arg6.bytes == op.arg(6)
    assert arg7.bytes == op.arg(7)
    assert arg8.bytes == op.arg(8)
    assert arg9.bytes == op.arg(9)
    assert arg10.bytes == op.arg(10)
    assert arg11.bytes == op.arg(11)
    assert arg12.bytes == op.arg(12)
    assert arg13.bytes == op.arg(13)
    assert arg14.bytes == op.arg(14)
    assert arg15.bytes == op.arg(15)
    assert arg16[0].bytes == op.arg(16)
    assert arg16[1].bytes == op.arg(17)
    assert arg17[0] == op.btoi(op.arg(18))
    assert arg17[1] == op.arg(19)
    assert arg18[0] == op.btoi(op.arg(20))
    assert arg18[1][0] == op.arg(21)
    assert arg18[1][1] == op.btoi(op.arg(22))
    assert arg19.bytes == op.arg(23)
    assert arg20.bytes == op.arg(24)

    # mutate all
    arg0 = arg0 + 1
    arg1 = arg1 + b"!"
    arg2 = arg2 + BigUInt(1)
    arg3 = String("hello_") + arg3
    arg4 = not arg4
    arg5 = arc4.UInt8(arg5.as_uint64() + 1)
    arg6 = arc4.UInt64(arg6.as_uint64() + 1)
    arg7 = arc4.UInt128(arg7.as_biguint() + BigUInt(1))
    arg8 = arc4.Address(op.Global.zero_address)
    arg9 = arc4.Bool(not arg9.native)
    arg10 = arc4.String(arg10.native + " world")
    arg11 = arc4.DynamicBytes(arg11.native + b"\x00")
    arg12[0] = arc4.Byte(0xFF)
    arg13 = SimpleStruct(x=arc4.UInt64(arg13.x.as_uint64() + 1), y=arg13.y)
    arg14 = NestedStruct(
        header=arc4.UInt8(arg14.header.as_uint64() + 1),
        data=arg14.data.copy(),
    )
    arg15 = arc4.Tuple(
        (
            arc4.UInt8(arg15[0].as_uint64() + 1),
            arc4.UInt64(arg15[1].as_uint64() + 1),
        )
    )
    arg16 = SimpleNamedTuple(
        a=arc4.UInt8(arg16.a.as_uint64() + 1),
        b=arc4.UInt64(arg16.b.as_uint64() + 1),
    )
    arg17 = (arg17[0] + 1, arg17[1] + b"!")
    arg18 = (arg18[0] + 1, (arg18[1][0] + b"!", arg18[1][1] + 1))
    arg19 = OverwriteStruct(
        value=arc4.UInt8(arg19.value.as_uint64() + 1),
        dont_overwrite_me=arc4.Bool(not arg19.dont_overwrite_me.native),
    )
    arg20.append(arc4.UInt8(0xFF))

    # assert all
    assert arg0 > 0
    assert arg1.length > 0
    assert arg2 > 0
    assert arg3.bytes.length > 0
    assert arg5.as_uint64() > 0
    assert arg6.as_uint64() > 0
    assert arg7.as_biguint() > 0
    assert arg8.native == op.Global.zero_address
    assert arg10.native.bytes.length > 0
    assert arg11.length > 0
    assert arg12[0] == arc4.Byte(0xFF)
    assert arg13.x.as_uint64() > 0
    assert arg14.header.as_uint64() > 0
    assert arg15[0].as_uint64() > 0
    assert arg16.a.as_uint64() > 0
    assert arg17[0] > 0
    assert arg17[1].length > 0
    assert arg18[0] > 0
    assert arg18[1][0].length > 0
    assert arg18[1][1] > 0
    assert arg19.value.as_uint64() > 0
    assert arg20.length > 0

    # some random cross-arg operations
    total = arg0 + arg5.as_uint64() + arg6.as_uint64() + arg15[1].as_uint64()
    total += arg16.b.as_uint64() + arg17[0] + arg18[0] + arg18[1][1]
    if arg4:
        total += arg1.length
    assert total > 0
    return arg9.native


@logicsig(validate_encoding="unsafe_disabled")
def args_complex_no_validation(
    arg0: UInt64,
    arg1: Bytes,
    arg2: BigUInt,
    arg3: String,
    arg4: bool,
    arg5: arc4.UInt8,
    arg6: arc4.UInt64,
    arg7: arc4.UInt128,
    arg8: arc4.Address,
    arg9: arc4.Bool,
    arg10: arc4.String,
    arg11: arc4.DynamicBytes,
    arg12: arc4.StaticArray[arc4.Byte, typing.Literal[4]],
    arg13: SimpleStruct,
    arg14: NestedStruct,
    arg15: arc4.Tuple[arc4.UInt8, arc4.UInt64],
    arg16: SimpleNamedTuple,
    arg17: tuple[UInt64, Bytes],
    arg18: tuple[UInt64, tuple[Bytes, UInt64]],
    arg19: OverwriteStruct,
    arg20: arc4.DynamicArray[arc4.UInt8],
) -> bool:
    # verify args match raw op.arg values
    assert arg0 == op.btoi(op.arg(0))
    assert arg1 == op.arg(1)
    assert arg2.bytes == op.arg(2)
    assert arg3.bytes == op.arg(3)
    assert arg4 == (op.btoi(op.arg(4)) != 0)
    assert arg5.bytes == op.arg(5)
    assert arg6.bytes == op.arg(6)
    assert arg7.bytes == op.arg(7)
    assert arg8.bytes == op.arg(8)
    assert arg9.bytes == op.arg(9)
    assert arg10.bytes == op.arg(10)
    assert arg11.bytes == op.arg(11)
    assert arg12.bytes == op.arg(12)
    assert arg13.bytes == op.arg(13)
    assert arg14.bytes == op.arg(14)
    assert arg15.bytes == op.arg(15)
    assert arg16[0].bytes == op.arg(16)
    assert arg16[1].bytes == op.arg(17)
    assert arg17[0] == op.btoi(op.arg(18))
    assert arg17[1] == op.arg(19)
    assert arg18[0] == op.btoi(op.arg(20))
    assert arg18[1][0] == op.arg(21)
    assert arg18[1][1] == op.btoi(op.arg(22))
    assert arg19.bytes == op.arg(23)
    assert arg20.bytes == op.arg(24)

    # mutate all
    arg0 = arg0 + 1
    arg1 = arg1 + b"!"
    arg2 = arg2 + BigUInt(1)
    arg3 = String("hello_") + arg3
    arg4 = not arg4
    arg5 = arc4.UInt8(arg5.as_uint64() + 1)
    arg6 = arc4.UInt64(arg6.as_uint64() + 1)
    arg7 = arc4.UInt128(arg7.as_biguint() + BigUInt(1))
    arg8 = arc4.Address(op.Global.zero_address)
    arg9 = arc4.Bool(not arg9.native)
    arg10 = arc4.String(arg10.native + " world")
    arg11 = arc4.DynamicBytes(arg11.native + b"\x00")
    arg12[0] = arc4.Byte(0xFF)
    arg13 = SimpleStruct(x=arc4.UInt64(arg13.x.as_uint64() + 1), y=arg13.y)
    arg14 = NestedStruct(
        header=arc4.UInt8(arg14.header.as_uint64() + 1),
        data=arg14.data.copy(),
    )
    arg15 = arc4.Tuple(
        (
            arc4.UInt8(arg15[0].as_uint64() + 1),
            arc4.UInt64(arg15[1].as_uint64() + 1),
        )
    )
    arg16 = SimpleNamedTuple(
        a=arc4.UInt8(arg16.a.as_uint64() + 1),
        b=arc4.UInt64(arg16.b.as_uint64() + 1),
    )
    arg17 = (arg17[0] + 1, arg17[1] + b"!")
    arg18 = (arg18[0] + 1, (arg18[1][0] + b"!", arg18[1][1] + 1))
    arg19 = OverwriteStruct(
        value=arc4.UInt8(arg19.value.as_uint64() + 1),
        dont_overwrite_me=arc4.Bool(not arg19.dont_overwrite_me.native),
    )
    arg20.append(arc4.UInt8(0xFF))

    # assert all
    assert arg0 > 0
    assert arg1.length > 0
    assert arg2 > 0
    assert arg3.bytes.length > 0
    assert arg5.as_uint64() > 0
    assert arg6.as_uint64() > 0
    assert arg7.as_biguint() > 0
    assert arg8.native == op.Global.zero_address
    assert arg10.native.bytes.length > 0
    assert arg11.length > 0
    assert arg12[0] == arc4.Byte(0xFF)
    assert arg13.x.as_uint64() > 0
    assert arg14.header.as_uint64() > 0
    assert arg15[0].as_uint64() > 0
    assert arg16.a.as_uint64() > 0
    assert arg17[0] > 0
    assert arg17[1].length > 0
    assert arg18[0] > 0
    assert arg18[1][0].length > 0
    assert arg18[1][1] > 0
    assert arg19.value.as_uint64() > 0
    assert arg20.length > 0

    return arg9.native
