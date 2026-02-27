from algopy import Bytes, UInt64, arc4, logicsig, op


@logicsig
def args_simple(arg0: UInt64, arg1: Bytes, arg2: bool) -> UInt64:
    # verify args match raw op.arg values
    assert arg0 == arc4.UInt64.from_bytes(op.arg(0)).native
    assert arg1 == arc4.DynamicBytes.from_bytes(op.arg(1)).native
    assert arg2 == arc4.Bool(op.btoi(op.arg(2)) != 0)

    # mutate all
    if arg0 < 10:
        arg0 = UInt64(10)
    arg1 = arg1 + b"suffix"
    arg2 = not arg2

    # assert all
    assert arg0 >= 10
    assert arg1.length > 0

    # some random cross-arg operations
    if arg2:
        arg0 += arg1.length
    return arg0
