import base64
import typing
from collections.abc import Generator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context, arc4
from algopy_testing.constants import MAX_UINT64, MAX_UINT512

from tests.common import AVMInvoker


class Swapped:
    a: algopy.String
    b: algopy.BigUInt
    c: algopy.UInt64
    d: algopy.Bytes
    e: int
    f: bool
    g: bytes
    h: str

    def __init__(  # noqa: PLR0913
        self,
        a: algopy.String,
        b: algopy.BigUInt,
        c: algopy.UInt64,
        d: algopy.Bytes,
        e: int,
        f: bool,  # noqa: FBT001
        g: bytes,
        h: str,
    ) -> None:
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f
        self.g = g
        self.h = h


class SwappedArc4(arc4.Struct):
    m: arc4.UIntN[typing.Literal[64]]
    n: arc4.BigUIntN[typing.Literal[256]]
    o: arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]
    p: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]
    q: arc4.Bool
    r: arc4.StaticArray[arc4.UInt8, typing.Literal[3]]
    s: arc4.DynamicArray[arc4.UInt16]
    t: arc4.Tuple[arc4.UInt32, arc4.UInt64, arc4.String]

    def __init__(  # noqa: PLR0913
        self,
        m: arc4.UIntN[typing.Literal[64]],
        n: arc4.BigUIntN[typing.Literal[256]],
        o: arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]],
        p: arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]],
        q: arc4.Bool,
        r: arc4.StaticArray[arc4.UInt8, typing.Literal[3]],
        s: arc4.DynamicArray[arc4.UInt16],
        t: arc4.Tuple[arc4.UInt32, arc4.UInt64, arc4.String],
    ) -> None:
        self.m = m
        self.n = n
        self.o = o
        self.p = p
        self.q = q
        self.r = r
        self.s = s
        self.t = t
        super().__init__(m, n, o, p, q, r, s, t)


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_emit(get_avm_result: AVMInvoker, context: AlgopyTestContext) -> None:
    _test_data = Swapped(
        algopy.String("hello"),
        MAX_UINT512,
        MAX_UINT64,
        algopy.Bytes(b"world"),
        16,
        False,  # noqa: FBT003
        b"test",
        "greetings",
    )

    dummy_app = context.any_application()
    context.set_transaction_group(
        [context.any_application_call_transaction(app_id=dummy_app)], active_transaction_index=0
    )

    _test_data_arc4 = SwappedArc4(
        arc4.UIntN[typing.Literal[64]](42),
        arc4.BigUIntN[typing.Literal[256]](512),
        arc4.UFixedNxM[typing.Literal[32], typing.Literal[8]]("42.94967295"),
        arc4.BigUFixedNxM[typing.Literal[256], typing.Literal[16]]("25.5"),
        arc4.Bool(True),  # noqa: FBT003
        arc4.StaticArray(arc4.UInt8(1), arc4.UInt8(2), arc4.UInt8(3)),
        arc4.DynamicArray(arc4.UInt16(1), arc4.UInt16(2), arc4.UInt16(3)),
        arc4.Tuple((arc4.UInt32(1), arc4.UInt64(2), arc4.String("hello"))),
    )
    avm_result = get_avm_result(
        "verify_emit",
        a=_test_data.a.value,
        b=_test_data.b,
        c=_test_data.c,
        d=_test_data.d.value,
        e=_test_data.e,
        f=_test_data.f,
        g=_test_data.g,
        h=_test_data.h,
        m=_test_data_arc4.m.native.value,
        n=_test_data_arc4.n.native.value,
        o=int.from_bytes(_test_data_arc4.o.bytes.value),
        p=int.from_bytes(_test_data_arc4.p.bytes.value),
        q=_test_data_arc4.q.native,
        r=_test_data_arc4.r.bytes.value,
        s=_test_data_arc4.s.bytes.value,
        t=_test_data_arc4.t.bytes.value,
    )
    arc4.emit(_test_data_arc4)
    arc4.emit(
        "Swapped(string,uint512,uint64,byte[],uint64,bool,byte[],string,uint64,uint256,ufixed32x8,ufixed256x16,bool,uint8[3],uint16[],(uint32,uint64,string))",
        _test_data.a,
        _test_data.b,
        _test_data.c,
        _test_data.d,
        _test_data.e,
        _test_data.f,
        _test_data.g,
        _test_data.h,
        _test_data_arc4.m,
        _test_data_arc4.n,
        _test_data_arc4.o,
        _test_data_arc4.p,
        _test_data_arc4.q,
        _test_data_arc4.r,
        _test_data_arc4.s,
        _test_data_arc4.t,
    )

    arc4.emit(
        "Swapped",
        _test_data.a,
        _test_data.b,
        _test_data.c,
        _test_data.d,
        _test_data.e,
        _test_data.f,
        _test_data.g,
        _test_data.h,
        _test_data_arc4.m,
        _test_data_arc4.n,
        _test_data_arc4.o,
        _test_data_arc4.p,
        _test_data_arc4.q,
        _test_data_arc4.r,
        _test_data_arc4.s,
        _test_data_arc4.t,
    )

    arc4_result = [
        base64.b64encode(log).decode() for log in context.get_application_logs(dummy_app.id)
    ]
    assert avm_result == arc4_result
