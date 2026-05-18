"""Pure constant-folding helpers for AVM intrinsics that are folded
only by GVN (multi-return ops; see `intrinsic_simplification.COMPILE_TIME_CONSTANT_OPS`
for the categorisation).

Each `fold_*` takes raw `int` inputs, returns the raw result tuple, or
returns `None` if the inputs would cause the op to fail at runtime
(out-of-range, overflow, divide-by-zero, etc.). No model imports.
"""

import enum
import hashlib
import math
import operator
import typing
from collections.abc import Callable, Mapping
from itertools import zip_longest

from puya import algo_constants, log
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import PrimitiveIRType
from puya.utils import sha512_256_hash

logger = log.get_logger(__name__)

_U64_MASK = (1 << 64) - 1


def fold_addw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    total = a + b
    return total >> 64, total & _U64_MASK


def fold_mulw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    product = a * b
    return product >> 64, product & _U64_MASK


def fold_expw(a: int, b: int) -> tuple[int, int] | None:
    if not (valid_uint64(a) and valid_uint64(b)):
        return None
    if a == 0 and b == 0:
        return None  # 0**0 traps on AVM
    result = a**b
    if result.bit_length() > 128:
        return None  # would overflow uint128
    return result >> 64, result & _U64_MASK


def fold_divw(hi: int, lo: int, divisor: int) -> int | None:
    if not (valid_uint64(hi) and valid_uint64(lo) and valid_uint64(divisor)):
        return None
    if divisor == 0:
        return None
    dividend = (hi << 64) | lo
    quotient = dividend // divisor
    if not valid_uint64(quotient):
        return None
    return quotient


def fold_divmodw(h1: int, l1: int, h2: int, l2: int) -> tuple[int, int, int, int] | None:
    if not all(valid_uint64(x) for x in (h1, l1, h2, l2)):
        return None
    divisor = (h2 << 64) | l2
    if divisor == 0:
        return None
    dividend = (h1 << 64) | l1
    q, r = divmod(dividend, divisor)
    return q >> 64, q & _U64_MASK, r >> 64, r & _U64_MASK


def _eval_sha256(arg: bytes) -> bytes:
    return hashlib.sha256(arg).digest()


def _eval_sha3_256(arg: bytes) -> bytes:
    return hashlib.sha3_256(arg).digest()


def _eval_keccak256(arg: bytes) -> bytes:
    from Cryptodome.Hash import keccak

    return keccak.new(data=arg, digest_bits=256).digest()


hash_eval_funcs: typing.Final[Mapping[AVMOp, Callable[[bytes], bytes]]] = {
    AVMOp.sha256: _eval_sha256,
    AVMOp.sha3_256: _eval_sha3_256,
    AVMOp.sha512_256: sha512_256_hash,
    AVMOp.keccak256: _eval_keccak256,
}


def valid_uint64(x: int) -> bool:
    return 0 <= x <= algo_constants.MAX_UINT64


def _byte_wise(op: Callable[[int, int], int], lhs: bytes, rhs: bytes) -> bytes:
    return bytes([op(a, b) for a, b in zip_longest(lhs[::-1], rhs[::-1], fillvalue=0)][::-1])


_EXTRACT_UINTN_BYTE_SIZE: typing.Final[Mapping[AVMOp, int]] = {
    AVMOp.extract_uint16: 2,
    AVMOp.extract_uint32: 4,
    AVMOp.extract_uint64: 8,
}


def fold_extract_uint_n(op: AVMOp, b: bytes, offset: int) -> int | None:
    byte_size = _EXTRACT_UINTN_BYTE_SIZE.get(op)
    if byte_size is None:
        return None
    extracted = b[offset : offset + byte_size]
    if len(extracted) != byte_size:
        return None
    return int.from_bytes(extracted, byteorder="big", signed=False)


def fold_setbit_uint64(source: int, index: int, value: int) -> int | None:
    if index >= 64:
        return None
    if value:
        return source | (1 << index)
    return source & ~(1 << index)


def fold_replace2(source: bytes, start: int, replacement: bytes) -> bytes | None:
    if start + len(replacement) > len(source):
        return None
    out = bytearray(source)
    out[start : start + len(replacement)] = replacement
    return bytes(out)


def fold_getbit_bytes(b: bytes, index: int) -> int | None:
    if index >= len(b) * 8:
        return None
    byte_index, bit_offset = divmod(index, 8)
    return (b[byte_index] >> (7 - bit_offset)) & 1


def fold_getbyte(b: bytes, index: int) -> int | None:
    if index >= len(b):
        return None
    return b[index]


def fold_setbit_bytes(b: bytes, index: int, value: int) -> bytes | None:
    if index >= len(b) * 8:
        return None
    byte_index, bit_offset = divmod(index, 8)
    mask = 1 << (7 - bit_offset)
    byte = b[byte_index]
    new_byte = byte | mask if value else byte & ~mask
    return b[:byte_index] + bytes([new_byte]) + b[byte_index + 1 :]


def fold_setbyte(b: bytes, index: int, value: int) -> bytes | None:
    if index >= len(b):
        return None
    if value > 0xFF:
        return None
    out = bytearray(b)
    out[index] = value
    return bytes(out)


def fold_uint64_const_unary_op(op: AVMOp, x: int) -> int | None:
    match op:
        case AVMOp.not_:
            return 0 if x else 1
        case AVMOp.bitwise_not:
            return x ^ 0xFFFFFFFFFFFFFFFF
        case AVMOp.sqrt:
            return math.isqrt(x)
        case AVMOp.bitlen:
            return x.bit_length()
    return None


def fold_bytes_const_unary_op(op: AVMOp, b: bytes) -> int | bytes | None:
    """Bytes-arg unary const folds. `bsqrt`/`btoi`/`bitlen` return int, `bitwise_not_bytes`
    returns bytes. Returns None on out-of-range inputs (`btoi` >8, `bsqrt` >64)."""
    match op:
        case AVMOp.bitwise_not_bytes:
            return bytes(x ^ 0xFF for x in b)
        case AVMOp.btoi:
            if len(b) > 8:
                return None
            return int.from_bytes(b, byteorder="big", signed=False)
        case AVMOp.bitlen:
            return int.from_bytes(b, byteorder="big", signed=False).bit_length()
        case AVMOp.bsqrt:
            if len(b) > 64:
                return None
            return math.isqrt(int.from_bytes(b, byteorder="big", signed=False))
    return None


def fold_uint64_const_binary_op(op: AVMOp, a_const: int, b_const: int) -> int | None:
    match op:
        case AVMOp.add:
            c = a_const + b_const
        case AVMOp.sub:
            c = a_const - b_const
        case AVMOp.mul:
            c = a_const * b_const
        case AVMOp.div_floor:
            if b_const == 0:
                return None
            c = a_const // b_const
        case AVMOp.mod:
            if b_const == 0:
                return None
            c = a_const % b_const
        case AVMOp.lt:
            c = 1 if a_const < b_const else 0
        case AVMOp.lte:
            c = 1 if a_const <= b_const else 0
        case AVMOp.gt:
            c = 1 if a_const > b_const else 0
        case AVMOp.gte:
            c = 1 if a_const >= b_const else 0
        case AVMOp.eq:
            c = 1 if a_const == b_const else 0
        case AVMOp.neq:
            c = 1 if a_const != b_const else 0
        case AVMOp.and_:
            c = 1 if (a_const and b_const) else 0
        case AVMOp.or_:
            c = 1 if (a_const or b_const) else 0
        case AVMOp.shl:
            if b_const >= 64:
                return None
            c = (a_const << b_const) % (2**64)
        case AVMOp.shr:
            if b_const >= 64:
                return None
            c = a_const >> b_const
        case AVMOp.exp:
            if a_const == 0 and b_const == 0:
                return None
            c = a_const**b_const
        case AVMOp.bitwise_or:
            c = a_const | b_const
        case AVMOp.bitwise_and:
            c = a_const & b_const
        case AVMOp.bitwise_xor:
            c = a_const ^ b_const
        case AVMOp.getbit:
            source, index = a_const, b_const
            if index >= 64:
                return None
            c = 1 if (source & (1 << index)) else 0
        case _:
            logger.debug(f"don't know how to simplify {a_const} {op.code} {b_const}")
            return None
    if not valid_uint64(c):
        return None
    return c


def fold_biguint_const_binary_op(op: AVMOp, a_const: int, b_const: int) -> int | None:
    match op:
        case AVMOp.add_bytes:
            c = a_const + b_const
        case AVMOp.sub_bytes:
            c = a_const - b_const
        case AVMOp.mul_bytes:
            c = a_const * b_const
        case AVMOp.div_floor_bytes:
            if b_const == 0:
                return None
            c = a_const // b_const
        case AVMOp.mod_bytes:
            if b_const == 0:
                return None
            c = a_const % b_const
        case AVMOp.lt_bytes:
            c = 1 if a_const < b_const else 0
        case AVMOp.lte_bytes:
            c = 1 if a_const <= b_const else 0
        case AVMOp.gt_bytes:
            c = 1 if a_const > b_const else 0
        case AVMOp.gte_bytes:
            c = 1 if a_const >= b_const else 0
        case AVMOp.eq_bytes:
            c = 1 if a_const == b_const else 0
        case AVMOp.neq_bytes:
            c = 1 if a_const != b_const else 0
        case _:
            return None
    if c < 0:
        return None
    return c


def fold_bytes_const_binary_op(op: AVMOp, a: bytes, b: bytes) -> int | bytes | None:
    match op:
        case AVMOp.eq:
            return 1 if a == b else 0
        case AVMOp.neq:
            return 1 if a != b else 0
        case AVMOp.bitwise_or_bytes:
            return _byte_wise(operator.or_, a, b)
        case AVMOp.bitwise_and_bytes:
            return _byte_wise(operator.and_, a, b)
        case AVMOp.bitwise_xor_bytes:
            return _byte_wise(operator.xor, a, b)
    return None


class BinarySimplification(enum.Enum):
    """Symbolic outcome for value-level binary-op simplifications.

    Callers map LEFT/RIGHT to their identity space (Value for the rewriter,
    VN for GVN).
    """

    LEFT = enum.auto()
    RIGHT = enum.auto()


def simplify_uint64_binary_op_one_const(
    op: AVMOp,
    a: models.Value,
    b: models.Value,
    a_const: int | None,
    b_const: int | None,
    *,
    bool_context: bool = False,
) -> int | BinarySimplification | None:
    """Algebraic simplification of `op(a, b)` when at least one operand is constant.

    Returns an int for a folded literal, LEFT/RIGHT for a pass-through to
    operand a/b, or None if no rule fires. Does NOT handle `op == AVMOp.eq` —
    each caller emits its own `!operand` rewrite (the rewrite shape is
    caller-specific).
    """

    def bool_safe(arg: models.Value) -> bool:
        return bool_context or arg.ir_type == PrimitiveIRType.bool

    match op:
        case AVMOp.gte:
            # a >= 0 <-> 1
            if b_const == 0:
                return 1
            # a >= 1 <-> a (in bool context)
            if b_const == 1 and bool_safe(a):
                return BinarySimplification.LEFT
        case AVMOp.lte:
            # 0 <= b <-> 1
            if a_const == 0:
                return 1
            # 1 <= b <-> b (in bool context)
            if a_const == 1 and bool_safe(b):
                return BinarySimplification.RIGHT
        case AVMOp.mul:
            if a_const == 1:
                return BinarySimplification.RIGHT
            if b_const == 1:
                return BinarySimplification.LEFT
            if 0 in (a_const, b_const):
                return 0
        case AVMOp.div_floor:
            if b_const == 1:
                return BinarySimplification.LEFT
        case AVMOp.mod:
            if b_const == 1:
                return 0
        case AVMOp.add:
            if a_const == 0:
                return BinarySimplification.RIGHT
            if b_const == 0:
                return BinarySimplification.LEFT
        case AVMOp.sub:
            if b_const == 0:
                return BinarySimplification.LEFT
        case AVMOp.and_:
            if 0 in (a_const, b_const):
                return 0
        case AVMOp.or_:
            if bool_context:
                if a_const == 0:
                    return BinarySimplification.RIGHT
                if b_const == 0:
                    return BinarySimplification.LEFT
        case AVMOp.neq:
            # 0 != b <-> b  /  a != 0 <-> a (in bool context)
            if a_const == 0 and bool_safe(b):
                return BinarySimplification.RIGHT
            if b_const == 0 and bool_safe(a):
                return BinarySimplification.LEFT
        case AVMOp.lt:
            # 0 < b <-> b (in bool context)
            if a_const == 0 and bool_safe(b):
                return BinarySimplification.RIGHT
        case AVMOp.gt:
            # a > 0 <-> a (in bool context)
            if b_const == 0 and bool_safe(a):
                return BinarySimplification.LEFT
    return None


def simplify_bytes_binary_op_one_const(
    op: AVMOp,
    a_const: int | None,
    b_const: int | None,
) -> int | BinarySimplification | None:
    """BigUInt-valued one-const algebra on bytes binary ops.

    Simpler than uint64's: no bool_context, no Value args, no eq carve-out.
    """
    match op:
        case AVMOp.mul_bytes:
            if a_const == 1:
                return BinarySimplification.RIGHT
            if b_const == 1:
                return BinarySimplification.LEFT
            if 0 in (a_const, b_const):
                return 0
        case AVMOp.add_bytes:
            if a_const == 0:
                return BinarySimplification.RIGHT
            if b_const == 0:
                return BinarySimplification.LEFT
        case AVMOp.sub_bytes:
            if b_const == 0:
                return BinarySimplification.LEFT
        case AVMOp.div_floor_bytes:
            if b_const == 1:
                return BinarySimplification.LEFT
        case AVMOp.mod_bytes:
            if b_const == 1:
                return 0
    return None
