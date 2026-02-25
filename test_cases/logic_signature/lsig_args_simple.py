from algopy import Bytes, UInt64, logicsig, op


@logicsig
def args_simple(arg0: UInt64, arg1: Bytes, arg2: bool) -> UInt64:
    # verify args match raw op.arg values
    assert arg0 == op.btoi(op.arg(0))
    assert arg1 == op.arg(1)
    assert arg2 == (op.btoi(op.arg(2)) != 0)

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
