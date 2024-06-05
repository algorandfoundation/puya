import base64
import math
import re
from pathlib import Path

import algokit_utils
import pytest
from algopy import BigUInt, UInt64, op
from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT64, MAX_UINT512
from algosdk.v2client.algod import AlgodClient

from tests.common import AVMInvoker, create_avm_invoker
from tests.util import get_sha256_hash, int_to_bytes

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "MiscellaneousOps" / "data" / "MiscellaneousOpsContract.arc32.json"


def _too_big_error(max_length: int) -> str:
    return re.escape(f"expected value <= {max_length}")


_too_big64_error = _too_big_error(MAX_UINT64)
_too_big512_error = _too_big_error(MAX_UINT512)

_avm_int_arg_overflow_error = "is not a non-negative int or is too big to fit in size"
_avm_bytes_arg_overflow_error = "math attempted on large byte-array"

_extract_out_of_bound_error = re.compile("extraction (start|end) \\d+ is beyond length")


@pytest.fixture(scope="module")
def get_ops_avm_result(algod_client: AlgodClient) -> AVMInvoker:
    return create_avm_invoker(APP_SPEC, algod_client)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, MAX_UINT64),
        (MAX_UINT64, 0),
        (1, 0),
        (0, 1),
        (100, 42),
        (1, MAX_UINT64 - 1),
        (MAX_UINT64 - 1, 1),
        (100, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_addw(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_addw", a=a, b=b)
    avm_result_tuples = _bytes_to_uint64_tuple(avm_result)
    result = op.addw(a, b)
    assert avm_result_tuples == result


@pytest.mark.parametrize(
    ("a", "b"),
    [(1, MAX_UINT64 + 1), (MAX_UINT64 + 1, 1), (0, MAX_UINT512), (MAX_UINT512 * 2, 0)],
)
def test_addw_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.addw(a, b)


@pytest.mark.parametrize(
    "a",
    [
        b"",
        b"abc",
        base64.b64encode(b"hello, world."),
        base64.b64encode(b"0123"),
        base64.b64encode(b"\xff"),
        base64.b64encode(b"\x00" * 256 + b"\xff"),
    ],
)
def test_base64_decode_standard(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    avm_result = get_ops_avm_result("verify_base64_decode_standard", a=a)
    result = op.base64_decode(op.Base64.StdEncoding, a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        b"\x00" * 256 + b"\xff",
        int_to_bytes(MAX_UINT512),
    ],
)
def test_base64_decode_standard_input_error(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    with pytest.raises(algokit_utils.LogicError, match="illegal base64 data"):
        get_ops_avm_result("verify_base64_decode_standard", a=a)
    with pytest.raises(ValueError, match="illegal base64 data"):
        op.base64_decode(op.Base64.StdEncoding, a)


@pytest.mark.parametrize(
    "a",
    [
        b"",
        b"abc",
        base64.urlsafe_b64encode(b"hello, world."),
        base64.urlsafe_b64encode(b"0123"),
        base64.urlsafe_b64encode(b"\xff"),
        base64.urlsafe_b64encode(b"\x00" * 256 + b"\xff"),
    ],
)
def test_base64_decode_url(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    avm_result = get_ops_avm_result("verify_base64_decode_url", a=a)
    result = op.base64_decode(op.Base64.URLEncoding, a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        b"\x00" * 256 + b"\xff",
        int_to_bytes(MAX_UINT512),
    ],
)
def test_base64_decode_url_input_error(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    with pytest.raises(algokit_utils.LogicError, match="illegal base64 data"):
        get_ops_avm_result("verify_base64_decode_url", a=a)
    with pytest.raises(ValueError, match="illegal base64 data"):
        op.base64_decode(op.Base64.URLEncoding, a)


@pytest.mark.parametrize(
    ("a", "pad_a_size"),
    [
        (int_to_bytes(0), 0),
        (int_to_bytes(1), 0),
        (int_to_bytes(MAX_UINT64), 0),
        (int_to_bytes(MAX_UINT512), 0),
        (int_to_bytes(MAX_UINT512 * MAX_UINT512), 0),
        (b"\x00" * 8 + b"\x0f" * 4, 0),
        (b"\x0f", MAX_BYTES_SIZE - 1),
    ],
)
def test_bytes_bitlen(get_ops_avm_result: AVMInvoker, a: bytes, pad_a_size: int) -> None:
    avm_result = get_ops_avm_result("verify_bytes_bitlen", a=a, pad_a_size=pad_a_size)
    result = op.bitlen(a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        0,
        1,
        42,
        MAX_UINT64,
    ],
)
def test_uint64_bitlen(get_ops_avm_result: AVMInvoker, a: int) -> None:
    avm_result = get_ops_avm_result("verify_uint64_bitlen", a=a)
    result = op.bitlen(a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [MAX_UINT64 + 1, MAX_UINT512, MAX_UINT512 * 2],
)
def test_uint64_bitlen_input_overflow(a: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.bitlen(a)


@pytest.mark.parametrize(
    "a",
    [0, 1, 2, 9, 13, MAX_UINT64, MAX_UINT512],
)
def test_bsqrt(get_ops_avm_result: AVMInvoker, a: int) -> None:
    a_bytes = int_to_bytes(a)
    avm_result = get_ops_avm_result("verify_bsqrt", a=a_bytes)
    assert avm_result == op.bsqrt(BigUInt(a)).bytes


@pytest.mark.parametrize(
    "a",
    [MAX_UINT512 + 1, MAX_UINT512 * 2],
)
def test_bsqrt_input_overflow(get_ops_avm_result: AVMInvoker, a: int) -> None:
    a_bytes = int_to_bytes(a)
    with pytest.raises(algokit_utils.LogicError, match=_avm_bytes_arg_overflow_error):
        get_ops_avm_result("verify_bsqrt", a=a_bytes)
    with pytest.raises(ValueError, match=_too_big512_error):
        op.bsqrt(BigUInt(a))


@pytest.mark.parametrize(
    "a",
    [
        int_to_bytes(0),
        int_to_bytes(1),
        int_to_bytes(MAX_UINT64),
        b"\x00" * 4 + b"\x0f" * 4,
    ],
)
def test_btoi(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    avm_result = get_ops_avm_result("verify_btoi", a=a)
    result = op.btoi(a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        int_to_bytes(MAX_UINT512),
        int_to_bytes(MAX_UINT512 * MAX_UINT512),
        b"\x00" * 5 + b"\x0f" * 4,
    ],
)
def test_btoi_input_overflow(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    with pytest.raises(
        algokit_utils.LogicError, match=re.escape(f"btoi arg too long, got [{len(a)}]bytes")
    ):
        get_ops_avm_result("verify_btoi", a=a)

    with pytest.raises(ValueError, match=re.escape(f"btoi arg too long, got [{len(a)}]bytes")):
        op.btoi(a)


@pytest.mark.parametrize(
    "a",
    [
        0,
        1,
        42,
        MAX_BYTES_SIZE,
    ],
)
def test_bzero(get_ops_avm_result: AVMInvoker, a: int) -> None:
    avm_result = get_ops_avm_result("verify_bzero", a=a)
    result = op.bzero(a)
    assert avm_result == get_sha256_hash(result)


@pytest.mark.parametrize(
    "a",
    [MAX_BYTES_SIZE + 1, MAX_UINT64],
)
def test_bzero_overflow(get_ops_avm_result: AVMInvoker, a: int) -> None:
    with pytest.raises(
        algokit_utils.LogicError, match="bzero attempted to create a too large string"
    ):
        get_ops_avm_result("verify_bzero", a=a)
    with pytest.raises(ValueError, match="bzero attempted to create a too large string"):
        op.bzero(a)


@pytest.mark.parametrize(
    "a",
    [MAX_UINT64 + 1, MAX_UINT512, MAX_UINT512 * 2],
)
def test_bzero_input_overflow(a: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.bzero(a)


@pytest.mark.parametrize(
    ("a", "b", "pad_a_size", "pad_b_size"),
    [
        (b"", b"", 0, 0),
        (b"1", b"", 0, 0),
        (b"", b"1", 0, 0),
        (b"1", b"1", 0, 0),
        (b"", b"0", 0, MAX_BYTES_SIZE - 1),
        (b"0", b"", MAX_BYTES_SIZE - 1, 0),
        (b"1", b"0", 0, MAX_BYTES_SIZE - 2),
        (b"1", b"0", MAX_BYTES_SIZE - 2, 0),
    ],
)
def test_concat(
    get_ops_avm_result: AVMInvoker, a: bytes, b: bytes, pad_a_size: int, pad_b_size: int
) -> None:
    avm_result = get_ops_avm_result(
        "verify_concat", a=a, b=b, pad_a_size=pad_a_size, pad_b_size=pad_b_size
    )
    a = (b"\x00" * pad_a_size) + a
    b = (b"\x00" * pad_b_size) + b
    assert avm_result == get_sha256_hash(op.concat(a, b))


@pytest.mark.parametrize(
    ("a", "b", "pad_a_size", "pad_b_size"),
    [
        (b"1", b"0", MAX_BYTES_SIZE, 0),
        (b"1", b"1", MAX_BYTES_SIZE, MAX_BYTES_SIZE),
        (b"1", b"0", 0, MAX_BYTES_SIZE),
    ],
)
def test_concat_input_overflow(
    get_ops_avm_result: AVMInvoker, a: bytes, b: bytes, pad_a_size: int, pad_b_size: int
) -> None:
    with pytest.raises(
        algokit_utils.LogicError, match=r"concat produced a too big \(\d+\) byte-array"
    ):
        get_ops_avm_result("verify_concat", a=a, b=b, pad_a_size=pad_a_size, pad_b_size=pad_b_size)
    a = (b"\x00" * pad_a_size) + a
    b = (b"\x00" * pad_b_size) + b

    with pytest.raises(ValueError, match=re.escape(f"expected value length <= {MAX_BYTES_SIZE}")):
        op.concat(a, b)


@pytest.mark.parametrize(
    ("a", "b", "c", "d"),
    [
        (0, 1, 0, 1),
        (100, 42, 100, 42),
        (42, 100, 42, 100),
        (0, MAX_UINT64, 0, MAX_UINT64),
        (MAX_UINT64, 1, MAX_UINT64, 1),
        (1, MAX_UINT64, 1, MAX_UINT64),
        (MAX_UINT64 - 1, 1, MAX_UINT64 - 1, 1),
        (1, MAX_UINT64 - 1, 1, MAX_UINT64 - 1),
        (100, MAX_UINT64, 100, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64, MAX_UINT64, MAX_UINT64),
    ],
)
def test_divmodw(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int, d: int) -> None:
    avm_result = get_ops_avm_result("verify_divmodw", a=a, b=b, c=c, d=d)
    avm_result_tuples = _bytes_to_uint64_tuple(avm_result)
    result = op.divmodw(a, b, c, d)
    assert avm_result_tuples == result


@pytest.mark.parametrize(
    ("a", "b", "c", "d"),
    [
        (1, MAX_UINT64 + 1, 1, MAX_UINT64 + 1),
        (MAX_UINT64 + 1, 1, MAX_UINT64 + 1, 1),
        (0, MAX_UINT512, 0, MAX_UINT512),
        (MAX_UINT512 * 2, 1, MAX_UINT512 * 2, 1),
    ],
)
def test_divmodw_input_overflow(a: int, b: int, c: int, d: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.divmodw(a, b, c, d)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (100, 42),
        (42, 100),
        (0, MAX_UINT64),
        (MAX_UINT64, 1),
        (1, MAX_UINT64),
        (MAX_UINT64 - 1, 1),
        (1, MAX_UINT64 - 1),
        (100, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_divmodw_zero_division(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="error"):
        get_ops_avm_result("verify_divmodw", a=a, b=b, c=0, d=0)

    with pytest.raises(ZeroDivisionError):
        op.divmodw(a, b, 0, 0)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (0, 1, 1),
        (42, 100, 100),
        (0, MAX_UINT64, MAX_UINT64),
        (1, MAX_UINT64, MAX_UINT64),
        (1, MAX_UINT64 - 1, MAX_UINT64 - 1),
        (100, MAX_UINT64, MAX_UINT64),
    ],
)
def test_divw(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int) -> None:
    avm_result = get_ops_avm_result("verify_divw", a=a, b=b, c=c)
    result = op.divw(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (100, 42, 42),
        (MAX_UINT64, 1, 1),
        (MAX_UINT64 - 1, 1, 1),
        (MAX_UINT64, MAX_UINT64, MAX_UINT64),
    ],
)
def test_divw_overflow(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="divw overflow"):
        get_ops_avm_result("verify_divw", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big64_error):
        op.divw(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (1, MAX_UINT64 + 1, 1),
        (MAX_UINT64 + 1, 1, MAX_UINT64 + 1),
        (0, MAX_UINT512, MAX_UINT512),
        (MAX_UINT512 * 2, 1, MAX_UINT512 * 2),
    ],
)
def test_divw_input_overflow(a: int, b: int, c: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.divw(a, b, c)


def test_err(get_ops_avm_result: AVMInvoker) -> None:
    with pytest.raises(algokit_utils.LogicError, match="err opcode executed"):
        get_ops_avm_result("verify_err")
    with pytest.raises(RuntimeError, match="err opcode executed"):
        op.err()


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (42, 11), (math.isqrt(MAX_UINT64), 2), (1, MAX_UINT64)],
)
def test_exp(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_exp", a=a, b=b)
    result = op.exp(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (100, 42),
        (MAX_UINT64, 2),
        (2, 64),
    ],
)
def test_exp_overflow(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="overflow"):
        get_ops_avm_result("verify_exp", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big64_error):
        op.exp(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, MAX_UINT64 + 1),
        (MAX_UINT64 + 1, 1),
        (0, MAX_UINT512),
        (MAX_UINT512 * 2, 1),
    ],
)
def test_exp_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.exp(a, b)


def test_exp_input_error(get_ops_avm_result: AVMInvoker) -> None:
    with pytest.raises(algokit_utils.LogicError, match=re.escape("0^0 is undefined")):
        get_ops_avm_result("verify_exp", a=0, b=0)
    with pytest.raises(ArithmeticError, match=re.escape("0^0 is undefined")):
        op.exp(0, 0)


@pytest.mark.parametrize(
    ("a", "b"),
    [(0, 1), (1, 0), (42, 11), (math.isqrt(MAX_UINT64), 4), (2, 127)],
)
def test_expw(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_expw", a=a, b=b)
    avm_result_tuples = _bytes_to_uint64_tuple(avm_result)
    result = op.expw(a, b)
    assert avm_result_tuples == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (100, 42),
        (MAX_UINT64, 3),
        (2, 128),
    ],
)
def test_expw_overflow(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="overflow"):
        get_ops_avm_result("verify_expw", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big64_error):
        op.expw(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, MAX_UINT64 + 1),
        (MAX_UINT64 + 1, 1),
        (0, MAX_UINT512),
        (MAX_UINT512 * 2, 1),
    ],
)
def test_expw_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.expw(a, b)


def test_expw_input_error(get_ops_avm_result: AVMInvoker) -> None:
    with pytest.raises(algokit_utils.LogicError, match=re.escape("0^0 is undefined")):
        get_ops_avm_result("verify_expw", a=0, b=0)
    with pytest.raises(ArithmeticError, match=re.escape("0^0 is undefined")):
        op.expw(0, 0)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 1),
        (100, 42),
        (42, 100),
        (0, MAX_UINT64),
        (MAX_UINT64, 1),
        (1, MAX_UINT64),
        (MAX_UINT64 - 1, 1),
        (1, MAX_UINT64 - 1),
        (100, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_divw_zero_division(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="error"):
        get_ops_avm_result("verify_divw", a=a, b=b, c=0)

    with pytest.raises(ZeroDivisionError):
        op.divw(a, b, 0)


@pytest.mark.parametrize(
    ("b", "c"),
    [
        (0, 0),
        (0, 1),
        (0, 2),
        (11, 1),
        (12, 0),
        (8, 4),
        (256, 0),
        (256, 3),
    ],
)
def test_extract(get_ops_avm_result: AVMInvoker, b: int, c: int) -> None:
    a = b"hello, world" * 30
    avm_result = get_ops_avm_result("verify_extract", a=a, b=b, c=c)
    result = op.extract(a, UInt64(b), UInt64(c))
    assert avm_result == result

    # when c is 0, `extract` op code works differently from `extract3` op code
    if c:
        result = op.extract(a, b, c)
        assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        b"hello, world",
        b"hi",
    ],
)
def test_extract_from_2_to_end(get_ops_avm_result: AVMInvoker, a: bytes) -> None:
    avm_result = get_ops_avm_result("verify_extract_from_2", a=a)
    result = op.extract(a, 2, 0)
    assert avm_result == result


@pytest.mark.parametrize(
    ("b", "c"),
    [
        (1, MAX_UINT64 + 1),
        (MAX_UINT64 + 1, 1),
        (0, MAX_UINT512),
        (MAX_UINT512 * 2, 1),
    ],
)
def test_extract_input_overflow(b: int, c: int) -> None:
    a = b"hello, world"
    with pytest.raises(ValueError, match=_too_big64_error):
        op.extract(a, b, c)


@pytest.mark.parametrize(
    ("b", "c"),
    [
        (0, 13),
        (13, 0),
        (11, 2),
        (8, 5),
    ],
)
def test_extract_input_error(get_ops_avm_result: AVMInvoker, b: int, c: int) -> None:
    a = b"hello, world"
    with pytest.raises(algokit_utils.LogicError, match=_extract_out_of_bound_error):
        get_ops_avm_result("verify_extract", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_extract_out_of_bound_error):
        op.extract(a, b, c)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (int_to_bytes(256), 0),
        (b"\x00" * 2 + int_to_bytes(256), 2),
        (int_to_bytes(MAX_UINT64), 6),
        (int_to_bytes(MAX_UINT512), 62),
    ],
)
def test_extract_uint16(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    avm_result = get_ops_avm_result("verify_extract_uint16", a=a, b=b)
    result = op.extract_uint16(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00" * 2 + int_to_bytes(256), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT64), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT512), MAX_UINT512),
    ],
)
def test_extract_uint16_input_overflow(a: bytes, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.extract_uint16(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (int_to_bytes(0), 0),
        (int_to_bytes(0), 1),
        (int_to_bytes(256), 1),
        (b"\x00" * 2 + int_to_bytes(256), 3),
        (int_to_bytes(MAX_UINT64), 8),
        (int_to_bytes(MAX_UINT512), 65),
    ],
)
def test_extract_uint16_input_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_extract_out_of_bound_error):
        get_ops_avm_result("verify_extract_uint16", a=a, b=b)
    with pytest.raises(ValueError, match=_extract_out_of_bound_error):
        op.extract_uint16(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x0ffff", 0),
        (b"\x00" * 4 + int_to_bytes(256), 2),
        (int_to_bytes(MAX_UINT64), 4),
        (int_to_bytes(MAX_UINT512), 60),
    ],
)
def test_extract_uint32(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    avm_result = get_ops_avm_result("verify_extract_uint32", a=a, b=b)
    result = op.extract_uint32(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00" * 4 + int_to_bytes(256), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT64), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT512), MAX_UINT512),
    ],
)
def test_extract_uint32_input_overflow(a: bytes, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.extract_uint32(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (int_to_bytes(0), 0),
        (int_to_bytes(0), 1),
        (int_to_bytes(256), 1),
        (b"\x00" * 4 + int_to_bytes(256), 3),
        (int_to_bytes(MAX_UINT64), 8),
        (int_to_bytes(MAX_UINT512), 65),
    ],
)
def test_extract_uint32_input_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_extract_out_of_bound_error):
        get_ops_avm_result("verify_extract_uint32", a=a, b=b)
    with pytest.raises(ValueError, match=_extract_out_of_bound_error):
        op.extract_uint32(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x0ffffffff", 0),
        (b"\x00" * 8 + int_to_bytes(256), 2),
        (int_to_bytes(MAX_UINT64), 0),
        (int_to_bytes(MAX_UINT512), 56),
    ],
)
def test_extract_uint64(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    avm_result = get_ops_avm_result("verify_extract_uint64", a=a, b=b)
    result = op.extract_uint64(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00" * 8 + int_to_bytes(256), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT64), MAX_UINT64 + 1),
        (int_to_bytes(MAX_UINT512), MAX_UINT512),
    ],
)
def test_extract_uint64_input_overflow(a: bytes, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.extract_uint64(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (int_to_bytes(0), 0),
        (int_to_bytes(0), 1),
        (int_to_bytes(256), 1),
        (b"\x00" * 8 + int_to_bytes(256), 3),
        (int_to_bytes(MAX_UINT64), 8),
        (int_to_bytes(MAX_UINT512), 65),
    ],
)
def test_extract_uint64_input_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match=_extract_out_of_bound_error):
        get_ops_avm_result("verify_extract_uint64", a=a, b=b)
    with pytest.raises(ValueError, match=_extract_out_of_bound_error):
        op.extract_uint64(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00", 0),
        (b"\x00" * 2 + int_to_bytes(256), 3),
        (b"\x00" * 2 + int_to_bytes(256), 0),
        (b"\x00" * 2 + int_to_bytes(256), 11),
        (b"\x00" * 2 + int_to_bytes(65535), 31),
        (b"\x00" * 2 + int_to_bytes(65535), 24),
        (int_to_bytes(MAX_UINT64), 63),
        (int_to_bytes(MAX_UINT64 - 1), 63),
        (int_to_bytes(MAX_UINT512), 511),
        (int_to_bytes(MAX_UINT512 - 1), 511),
        (int_to_bytes(MAX_UINT64), 0),
        (int_to_bytes(MAX_UINT512), 0),
    ],
)
def test_getbit_bytes(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    avm_result = get_ops_avm_result("verify_getbit_bytes", a=a, b=b)
    result = op.getbit(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00", 8),
        (int_to_bytes(MAX_UINT64), 64),
        (int_to_bytes(MAX_UINT64 - 1), 64),
        (int_to_bytes(MAX_UINT512), 512),
        (int_to_bytes(MAX_UINT512 - 1), 512),
    ],
)
def test_getbit_bytes_index_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="getbit index beyond byteslice"):
        get_ops_avm_result("verify_getbit_bytes", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big_error(len(a) * 8 - 1)):
        op.getbit(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (0, 3),
        (0, 10),
        (256, 3),
        (256, 0),
        (256, 11),
        (65535, 15),
        (65535, 7),
        (65535, 63),
        (MAX_UINT64, 63),
        (MAX_UINT64 - 1, 63),
        (MAX_UINT64, 0),
    ],
)
def test_getbit_uint64(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_getbit_uint64", a=a, b=b)
    result = op.getbit(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (MAX_UINT64, 64),
        (MAX_UINT64 - 1, 64),
    ],
)
def test_getbit_uint64_index_error(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="getbit index > 63"):
        get_ops_avm_result("verify_getbit_uint64", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big_error(7 if a == 0 else a.bit_length() - 1)):
        op.getbit(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00", 0),
        (b"\x00" * 2 + int_to_bytes(256), 3),
        (b"\x00" * 2 + int_to_bytes(256), 0),
        (b"\x00" * 2 + int_to_bytes(256), 1),
        (b"\x00" * 2 + int_to_bytes(65530), 3),
        (int_to_bytes(MAX_UINT64), 7),
        (int_to_bytes(MAX_UINT64 - 1), 0),
        (int_to_bytes(MAX_UINT64 - 1), 7),
        (int_to_bytes(MAX_UINT512), 63),
        (int_to_bytes(MAX_UINT512 - 1), 63),
        (int_to_bytes(MAX_UINT512), 0),
    ],
)
def test_getbyte(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    avm_result = get_ops_avm_result("verify_getbyte", a=a, b=b)
    result = op.getbyte(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b"\x00", 8),
        (int_to_bytes(MAX_UINT64), 64),
        (int_to_bytes(MAX_UINT64 - 1), 64),
        (int_to_bytes(MAX_UINT512), 512),
        (int_to_bytes(MAX_UINT512 - 1), 512),
    ],
)
def test_getbyte_index_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="getbyte index beyond array length"):
        get_ops_avm_result("verify_getbyte", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big_error(len(a) - 1)):
        op.getbyte(a, b)


@pytest.mark.parametrize(
    ("a"),
    [
        0,
        42,
        100,
        256,
        65535,
        MAX_UINT64,
    ],
)
def test_itob(get_ops_avm_result: AVMInvoker, a: int) -> None:
    avm_result = get_ops_avm_result("verify_itob", a=a)
    result = op.itob(a)
    assert avm_result == result


@pytest.mark.parametrize(
    "a",
    [
        MAX_UINT64 + 1,
        MAX_UINT512,
    ],
)
def test_itob_input_overflow(a: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.itob(a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (0, 1),
        (100, 42),
        (1, MAX_UINT64 - 1),
        (MAX_UINT64 - 1, 1),
        (100, MAX_UINT64),
        (MAX_UINT64, MAX_UINT64),
    ],
)
def test_mulw(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_mulw", a=a, b=b)
    avm_result_tuples = _bytes_to_uint64_tuple(avm_result)
    result = op.mulw(a, b)
    assert avm_result_tuples == result


@pytest.mark.parametrize(
    ("a", "b"),
    [(1, MAX_UINT64 + 1), (MAX_UINT64 + 1, 1), (0, MAX_UINT512), (MAX_UINT512 * 2, 0)],
)
def test_mulw_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.mulw(a, b)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"hello, world.", 5, b"!!"),
        (b"hello, world.", 5, b""),
        (b"hello, world.", 5, b", there."),
        (b"hello, world.", 12, b"!"),
        (b"hello, world.", 12, b""),
        (b"hello, world.", 0, b"H"),
        (b"", 0, b""),
    ],
)
def test_replace(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: bytes) -> None:
    avm_result = get_ops_avm_result("verify_replace", a=a, b=b, c=c)
    result = op.replace(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"", 0, b"A"),
        (b"hello", 5, b"!!"),
        (b"hello", 6, b"!"),
        (b"hello", 0, b"Hello, world"),
    ],
)
def test_replace_input_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: bytes) -> None:
    with pytest.raises(
        algokit_utils.LogicError,
        match=re.compile(r"replacement (start|end) \d+ beyond (original )*length"),
    ):
        get_ops_avm_result("verify_replace", a=a, b=b, c=c)

    with pytest.raises(ValueError, match=_too_big_error(len(a))):
        op.replace(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"one", b"two", 0),
        (b"one", b"two", 1),
        (b"one", b"two", 2),
        (b"one", b"two", True),
        (b"one", b"two", False),
        (b"\x00\x00\xff", b"\xff", 0),
        (b"\x00\x00\xff", b"\xff", 1),
    ],
)
def test_select_bytes(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes, c: int | bool) -> None:
    avm_result = get_ops_avm_result("verify_select_bytes", a=a, b=b, c=c)
    result = op.select_bytes(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"\x00\x00\xff", b"\xff", MAX_UINT64 + 1),
        (b"\x00\x00\xff", b"\xff", MAX_UINT512),
    ],
)
def test_select_bytes_input_overflow(a: bytes, b: bytes, c: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.select_bytes(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (10, 20, 0),
        (10, 20, 1),
        (10, 20, 2),
        (10, 20, True),
        (10, 20, False),
    ],
)
def test_select_uint64(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int | bool) -> None:
    avm_result = get_ops_avm_result("verify_select_uint64", a=a, b=b, c=c)
    result = op.select_uint64(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (MAX_UINT64 + 1, MAX_UINT64 + 10, MAX_UINT64 + 1),
        (MAX_UINT512, MAX_UINT512, MAX_UINT512),
    ],
)
def test_select_uint64_input_overflow(a: int, b: int, c: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.select_uint64(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"\x00", 0, 1),
        (b"\x00" * 2 + int_to_bytes(256), 3, 1),
        (b"\x00" * 2 + int_to_bytes(256), 0, 1),
        (b"\x00" * 2 + int_to_bytes(256), 11, 1),
        (b"\x00" * 2 + int_to_bytes(65535), 31, 0),
        (b"\x00" * 2 + int_to_bytes(65535), 24, 0),
        (int_to_bytes(MAX_UINT64), 63, 0),
        (int_to_bytes(MAX_UINT64 - 1), 63, 1),
        (int_to_bytes(MAX_UINT512), 511, 0),
        (int_to_bytes(MAX_UINT512 - 1), 511, 1),
        (int_to_bytes(MAX_UINT64), 0, 0),
        (int_to_bytes(MAX_UINT512), 0, 0),
    ],
)
def test_setbit_bytes(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int) -> None:
    avm_result = get_ops_avm_result("verify_setbit_bytes", a=a, b=b, c=c)
    result = op.setbit_bytes(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"\x00", 8, 1),
        (int_to_bytes(MAX_UINT64), 64, 0),
        (int_to_bytes(MAX_UINT64 - 1), 64, 1),
        (int_to_bytes(MAX_UINT512), 512, 0),
        (int_to_bytes(MAX_UINT512 - 1), 512, 1),
    ],
)
def test_setbit_bytes_index_error(
    get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int
) -> None:
    with pytest.raises(algokit_utils.LogicError, match="setbit index beyond byteslice"):
        get_ops_avm_result("verify_setbit_bytes", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(len(a) * 8 - 1)):
        op.setbit_bytes(a, b, c)


def test_setbit_bytes_bit_error(get_ops_avm_result: AVMInvoker) -> None:
    a = b"\x00"
    b = 0
    c = 2
    with pytest.raises(algokit_utils.LogicError, match="setbit value > 1"):
        get_ops_avm_result("verify_setbit_bytes", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(1)):
        op.setbit_bytes(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (0, 0, 1),
        (0, 3, 1),
        (0, 10, 1),
        (256, 3, 1),
        (256, 0, 1),
        (256, 11, 1),
        (65535, 15, 0),
        (65535, 7, 0),
        (65535, 63, 1),
        (MAX_UINT64, 63, 0),
        (MAX_UINT64 - 1, 63, 1),
        (MAX_UINT64, 0, 0),
    ],
)
def test_setbit_uint64(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int) -> None:
    avm_result = get_ops_avm_result("verify_setbit_uint64", a=a, b=b, c=c)
    result = op.setbit_uint64(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (MAX_UINT64, 64, 0),
        (MAX_UINT64 - 1, 64, 1),
    ],
)
def test_setbit_uint64_index_error(get_ops_avm_result: AVMInvoker, a: int, b: int, c: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="setbit index > 63 with Uint"):
        get_ops_avm_result("verify_setbit_uint64", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(7 if a == 0 else a.bit_length() - 1)):
        op.setbit_uint64(a, b, c)


def test_setbit_uint64_bit_error(get_ops_avm_result: AVMInvoker) -> None:
    a = 0
    b = 0
    c = 2
    with pytest.raises(algokit_utils.LogicError, match="setbit value > 1"):
        get_ops_avm_result("verify_setbit_uint64", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(1)):
        op.setbit_uint64(a, b, c)


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"\x00", 0, 1),
        (b"\x00" * 2 + int_to_bytes(256), 3, 1),
        (b"\x00" * 2 + int_to_bytes(256), 0, 1),
        (b"\x00" * 2 + int_to_bytes(256), 1, 255),
        (b"\x00" * 2 + int_to_bytes(65535), 2, 0),
        (b"\x00" * 2 + int_to_bytes(65535), 2, 100),
        (int_to_bytes(MAX_UINT64), 7, 0),
        (int_to_bytes(MAX_UINT64 - 1), 0, 42),
        (int_to_bytes(MAX_UINT512), 63, 0),
        (int_to_bytes(MAX_UINT512 - 1), 1, 1),
        (int_to_bytes(MAX_UINT64), 0, 0),
        (int_to_bytes(MAX_UINT512), 0, 0),
    ],
)
def test_setbyte(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int) -> None:
    avm_result = get_ops_avm_result("verify_setbyte", a=a, b=b, c=c)
    result = op.setbyte(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"\x00", 8, 1),
        (int_to_bytes(MAX_UINT64), 64, 0),
        (int_to_bytes(MAX_UINT64 - 1), 64, 1),
        (int_to_bytes(MAX_UINT512), 512, 0),
        (int_to_bytes(MAX_UINT512 - 1), 512, 1),
    ],
)
def test_setbyte_index_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="setbyte index beyond array length"):
        get_ops_avm_result("verify_setbyte", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(len(a) - 1)):
        op.setbyte(a, b, c)


def test_setbyte_byte_error(get_ops_avm_result: AVMInvoker) -> None:
    a = b"\x00"
    b = 0
    c = 256
    with pytest.raises(algokit_utils.LogicError, match="setbyte value > 255"):
        get_ops_avm_result("verify_setbyte", a=a, b=b, c=c)
    with pytest.raises(ValueError, match=_too_big_error(255)):
        op.setbyte(a, b, c)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (0, 1),
        (42, 0),
        (100, 42),
        (1, 63),
        (MAX_UINT64 - 1, 63),
        (MAX_UINT64, 63),
    ],
)
def test_shl(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_shl", a=a, b=b)
    result = op.shl(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [(1, MAX_UINT64 + 1), (MAX_UINT64 + 1, 1), (0, MAX_UINT512), (MAX_UINT512 * 2, 0)],
)
def test_shl_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match="expected value <="):
        op.shl(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, MAX_UINT64),
        (MAX_UINT64, 64),
    ],
)
def test_shl_input_error(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="shl arg too big"):
        get_ops_avm_result("verify_shl", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big_error(63)):
        op.shl(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (0, 0),
        (1, 0),
        (0, 1),
        (111, 42),
        (1, 63),
        (MAX_UINT64 - 1, 63),
        (MAX_UINT64, 63),
    ],
)
def test_shr(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    avm_result = get_ops_avm_result("verify_shr", a=a, b=b)
    result = op.shr(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, MAX_UINT64 + 1),
        (MAX_UINT64 + 1, 1),
        (0, MAX_UINT512),
        (MAX_UINT512 * 2, 1),
    ],
)
def test_shr_input_overflow(a: int, b: int) -> None:
    with pytest.raises(ValueError, match="expected value <="):
        op.shr(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (1, MAX_UINT64),
        (MAX_UINT64, 64),
    ],
)
def test_shr_input_error(get_ops_avm_result: AVMInvoker, a: int, b: int) -> None:
    with pytest.raises(algokit_utils.LogicError, match="shr arg too big"):
        get_ops_avm_result("verify_shr", a=a, b=b)
    with pytest.raises(ValueError, match=_too_big_error(63)):
        op.shr(a, b)


@pytest.mark.parametrize(
    "a",
    [
        0,
        1,
        2,
        9,
        13,
        MAX_UINT64,
    ],
)
def test_sqrt(get_ops_avm_result: AVMInvoker, a: int) -> None:
    avm_result = get_ops_avm_result("verify_sqrt", a=a)
    assert avm_result == op.sqrt(UInt64(a))


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"hello, world.", 5, 5),
        (b"hello, world.", 5, 6),
        (b"hello, world.", 5, 7),
        (b"hello, world.", 12, 13),
        (b"hello, world.", 11, 13),
        (b"hello, world.", 0, 1),
        (b"hello, world.", 0, 2),
        (b"hello, world.", 0, 13),
        (b"", 0, 0),
    ],
)
def test_substring(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int) -> None:
    avm_result = get_ops_avm_result("verify_substring", a=a, b=b, c=c)
    result = op.substring(a, b, c)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        (b"", 0, 1),
        (b"hello", 5, 7),
        (b"hello", 4, 3),
        (b"hello", 0, 7),
    ],
)
def test_substring_input_error(get_ops_avm_result: AVMInvoker, a: bytes, b: int, c: int) -> None:
    with pytest.raises(
        algokit_utils.LogicError,
        match=re.compile("(substring range beyond length of string)|(substring end before start)"),
    ):
        get_ops_avm_result("verify_substring", a=a, b=b, c=c)

    with pytest.raises(ValueError, match="expected value <="):
        op.substring(a, b, c)


@pytest.mark.parametrize(
    "a",
    [MAX_UINT64 + 1, MAX_UINT512, MAX_UINT512 * 2],
)
def test_sqrt_input_overflow(a: int) -> None:
    with pytest.raises(ValueError, match=_too_big64_error):
        op.sqrt(UInt64(a))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key0": "hello","key1": "world"}', b"key0"),
        (b'{"key0": 1,"key1": {"key2":2,"key2":"10"}, "key2": "test"}', b"key2"),
        (b'{"key0": "\\ud801\\udc37"}', b"key0"),
        (b'{"key0": "\\ud800\\ud800n"}', b"key0"),
    ],
)
def test_json_ref_string(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_ops_avm_result("verify_json_ref_string", a=a, b=b)
    result = op.JsonRef.json_string(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key0": 0,"key1": 1}', b"key1"),
        (f'{{"key0": 0,"key1": {MAX_UINT64}}}'.encode(), b"key1"),
        (b'{"key0": 1,"key1": {"key2":2,"key2":"10"}, "key2": 42}', b"key2"),
        (('{"key0": 1, "key1": ' + str(MAX_UINT64) + "}").encode(), b"key1"),
    ],
)
def test_json_ref_uint64(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_ops_avm_result("verify_json_ref_uint64", a=a, b=b)
    result = op.JsonRef.json_uint64(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (f'{{"key0": 0,"key1": {MAX_UINT64 + 1}}}'.encode(), b"key1"),
        (f'{{"key0": 0,"key1": {MAX_UINT512}}}'.encode(), b"key1"),
    ],
)
def test_json_ref_uint64_overflow(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    with pytest.raises(
        algokit_utils.LogicError,
        match=re.compile(r"cannot unmarshal .* into Go value of type uint64"),
    ):
        get_ops_avm_result("verify_json_ref_uint64", a=a, b=b)

    with pytest.raises(ValueError, match=_too_big64_error):
        op.JsonRef.json_uint64(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key0": 1,"key1": {"key2":2,"key2":"10"}, "key2": "test"}', b"key1"),
        (
            b'{"key0":1,"key1":{"key2":2,"key2":{"key5":"abc","key6":{"key7":"def","key7":"jkl"}}},"key2":"test"}',
            b"key1",
        ),
        (b'{"key0": {"key1":"\\ud801\\udc37"}}', b"key0"),
    ],
)
def test_json_ref_object(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    avm_result = get_ops_avm_result("verify_json_ref_object", a=a, b=b)
    result = op.JsonRef.json_object(a, b)
    assert avm_result == result


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key0": "hello","key1": "world"}', b""),
        (b'{"key0": 1,"key1": {"key2":2,"key2":"10"}, "key2": "test"}', b"key3"),
    ],
)
def test_json_ref_missing_key(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    key_error = re.compile("key .* not found in JSON text")
    with pytest.raises(algokit_utils.LogicError, match=key_error):
        get_ops_avm_result("verify_json_ref_string", a=a, b=b)

    with pytest.raises(algokit_utils.LogicError, match=key_error):
        get_ops_avm_result("verify_json_ref_uint64", a=a, b=b)

    with pytest.raises(algokit_utils.LogicError, match=key_error):
        get_ops_avm_result("verify_json_ref_object", a=a, b=b)

    with pytest.raises(ValueError, match=key_error):
        op.JsonRef.json_string(a, b)

    with pytest.raises(ValueError, match=key_error):
        op.JsonRef.json_uint64(a, b)

    with pytest.raises(ValueError, match=key_error):
        op.JsonRef.json_object(a, b)


def test_json_ref_wrong_return_type(get_ops_avm_result: AVMInvoker) -> None:
    a = b'{"key0": 1,"key1": {"key2":2,"key2":"10"}, "key2": "test"}'

    def _avm_return_type_error(t: str) -> re.Pattern[str]:
        return re.compile(rf"cannot unmarshal .* into Go value of type {re.escape(t)}")

    with pytest.raises(algokit_utils.LogicError, match=_avm_return_type_error("string")):
        get_ops_avm_result("verify_json_ref_string", a=a, b=b"key1")

    with pytest.raises(algokit_utils.LogicError, match=_avm_return_type_error("uint64")):
        get_ops_avm_result("verify_json_ref_uint64", a=a, b=b"key2")

    with pytest.raises(
        algokit_utils.LogicError, match=_avm_return_type_error("map[string]json.RawMessage")
    ):
        get_ops_avm_result("verify_json_ref_object", a=a, b=b"key0")

    with pytest.raises(TypeError, match="value must be a string type"):
        op.JsonRef.json_string(a, b"key1")

    with pytest.raises(TypeError, match="value must be a numeric type"):
        op.JsonRef.json_uint64(a, b"key2")

    with pytest.raises(TypeError, match="value must be an object type"):
        op.JsonRef.json_object(a, b"key0")

    # a =b'{"key": 1.2E-6}',
    # b = b"key"
    # (b'{"key0": 1,"key1": [2, "10"], "key2": "test"}', b"key1"),


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key0": "hello"', b"key0"),
        (b'{"key0": 0xFF}', b"key0"),
        (b'{"key": "algo",,,}', b"key"),
        (b'{"key0": [1,/*comment*/,3]}', b"key0"),
        (b'{"key0": 1,"key0": 2}', b"key0"),
        (b'{"key0": "\\uFF"}', b"key0"),
        (b'\\uFEFF{"key0": 1}', b"key0"),
    ],
)
def test_json_ref_invalid_json(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    json_error = re.compile("error while parsing JSON text, invalid json text")
    with pytest.raises(algokit_utils.LogicError, match=json_error):
        get_ops_avm_result("verify_json_ref_string", a=a, b=b)

    with pytest.raises(algokit_utils.LogicError, match=json_error):
        get_ops_avm_result("verify_json_ref_uint64", a=a, b=b)

    with pytest.raises(algokit_utils.LogicError, match=json_error):
        get_ops_avm_result("verify_json_ref_object", a=a, b=b)

    with pytest.raises(ValueError, match=json_error):
        op.JsonRef.json_string(a, b)

    with pytest.raises(ValueError, match=json_error):
        op.JsonRef.json_uint64(a, b)

    with pytest.raises(ValueError, match=json_error):
        op.JsonRef.json_object(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (b'{"key": 1.2E-6}', b"key"),
        (b'{"key": 0.2E+8}', b"key"),
        (b'{"key0": 1,"key1": [2, "10"], "key2": "test"}', b"key1"),
    ],
)
def test_json_ref_unsupported_types(get_ops_avm_result: AVMInvoker, a: bytes, b: bytes) -> None:
    def _avm_return_type_error(t: str) -> re.Pattern[str]:
        return re.compile(rf"cannot unmarshal .* into Go value of type {re.escape(t)}")

    with pytest.raises(algokit_utils.LogicError, match=_avm_return_type_error("string")):
        get_ops_avm_result("verify_json_ref_string", a=a, b=b)

    with pytest.raises(algokit_utils.LogicError, match=_avm_return_type_error("uint64")):
        get_ops_avm_result("verify_json_ref_uint64", a=a, b=b)

    with pytest.raises(
        algokit_utils.LogicError, match=_avm_return_type_error("map[string]json.RawMessage")
    ):
        get_ops_avm_result("verify_json_ref_object", a=a, b=b)

    with pytest.raises(TypeError, match="value must be a string type"):
        op.JsonRef.json_string(a, b)

    with pytest.raises(TypeError, match="value must be a numeric type"):
        op.JsonRef.json_uint64(a, b)

    with pytest.raises(TypeError, match="value must be an object type"):
        op.JsonRef.json_object(a, b)


def _bytes_to_uint64_tuple(x: object) -> tuple[UInt64, ...] | None:
    if isinstance(x, bytes | tuple | list):
        return tuple([UInt64(i) for i in x])
    return None
