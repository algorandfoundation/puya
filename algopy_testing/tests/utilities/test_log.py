import base64
import typing
from collections.abc import Generator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context, arc4
from algopy_testing.constants import MAX_UINT64, MAX_UINT512
from algopy_testing.utilities.log import log

from tests.common import AVMInvoker


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_log(get_avm_result: AVMInvoker, context: AlgopyTestContext) -> None:
    a = algopy.String("hello")
    b = algopy.UInt64(MAX_UINT64)
    c = algopy.Bytes(b"world")
    d = algopy.BigUInt(MAX_UINT512)
    e = arc4.Bool(True)  # noqa: FBT003
    f = arc4.String("greetings")
    g: arc4.UIntN[typing.Literal[64]] = arc4.UIntN[typing.Literal[64]](42)
    h: arc4.BigUIntN[typing.Literal[256]] = arc4.BigUIntN[typing.Literal[256]](512)
    i = arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]("42.94967295")
    j = arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("25.5")
    k = arc4.StaticArray[arc4.UInt8, typing.Literal[3]](
        arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3)
    )
    m = arc4.DynamicArray(arc4.UInt16(1), arc4.UInt16(2), arc4.UInt16(3))
    n = arc4.Tuple((arc4.UInt32(1), arc4.UInt64(2), arc4.String("hello")))

    avm_result = get_avm_result(
        "verify_log",
        a=a.value,
        b=b.value,
        c=c.value,
        d=d.bytes.value,
        e=e.native,
        f=f.native.value,
        g=g.native.value,
        h=h.native.value,
        i=int.from_bytes(i.bytes.value),
        j=int.from_bytes(j.bytes.value),
        k=k.bytes.value,
        m=m.bytes.value,
        n=n.bytes.value,
    )

    with pytest.raises(
        ValueError, match="Cannot emit events outside of application call context!"
    ):
        log(a, b, c, d, e, f, g, h, i, j, k, m, n, sep=b"-")

    dummy_app = context.any_application()
    context.set_transaction_group(
        [context.any_application_call_transaction(app_id=dummy_app)], active_transaction_index=0
    )
    log(a, b, c, d, e, f, g, h, i, j, k, m, n, sep=b"-")
    arc4_result = [
        base64.b64encode(log).decode() for log in context.get_application_logs(dummy_app.id)
    ]
    assert avm_result == arc4_result
