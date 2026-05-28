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
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.utils import sha512_256_hash

logger = log.get_logger(__name__)


PURE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        # `txn FirstValidTime` technically could fail, but shouldn't happen on mainnet?
        "txn",
        "sha256",
        "keccak256",
        "sha3_256",
        "sha512_256",
        "bitlen",
        # group: could only fail on a type error
        "!",
        "!=",
        "&",
        "&&",
        "<",
        "<=",
        "==",
        ">",
        ">=",
        "|",
        "||",
        "~",
        "addw",
        "mulw",
        "itob",
        "len",
        "select",
        "sqrt",
        "shl",
        "shr",
        "b&",
        "b|",
        "b~",
        # group: fail if an input is zero
        "%",
        "/",
        "expw",
        "divmodw",
        "divw",
        # group: fail on over/underflow
        "*",
        "+",
        "-",
        "^",
        "exp",
        # group: fail on index out of bounds
        "arg",
        "arg_0",
        "arg_1",
        "arg_2",
        "arg_3",
        "args",
        "extract",
        "extract3",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "getbit",
        "getbyte",
        "gaid",
        "gaids",
        "gload",
        "gloads",
        "gloadss",
        "substring",
        "substring3",
        "txna",
        "txnas",
        "gtxn",
        "gtxna",
        "gtxnas",
        "gtxns",
        "gtxnsa",
        "gtxnsas",
        "block",
        # group: fail on input too large
        "b%",
        "b*",
        "b+",
        "b-",
        "b/",
        "b^",
        "btoi",
        "b!=",
        "b<",
        "b<=",
        "b==",
        "b>",
        "b>=",
        "bsqrt",
        # group: fail on output too large
        "concat",
        "bzero",
        # group: fail on input format / byte lengths
        "base64_decode",
        "json_ref",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ec_add",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ec_multi_scalar_mul",
        "ec_map_to",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "vrf_verify",
        "falcon_verify",
        "mimc",
        # AVM vNext ops (currently v13)
        "poseidon2",
        "sha512",
        "sumhash512",
    ]
)

# ops that have no observable side effects outside the function
# note: originally generated basd on all ops that:
#       - return a stack value (this, as of v10, yields no false negatives)
#       - AND isn't in the generate_avm_ops.py list of exclusions (which are all control flow
#             or pure stack manipulations)
#       - AND isn't box_create or box_del, they were the only remaining false positives
IMPURE_SIDE_EFFECT_FREE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        "global",  # OpcodeBudget is non-const, otherwise this could be pure
        # group: could only fail on a type error
        "app_global_get",
        "app_global_get_ex",
        "load",
        # group: fail on resource not "available"
        # TODO: determine if any of this group is pure
        "acct_params_get",
        "app_opted_in",
        "app_params_get",
        "asset_holding_get",
        "asset_params_get",
        "app_local_get",
        "app_local_get_ex",
        "balance",
        "min_balance",
        "box_extract",
        "box_get",
        "box_len",
        # group: fail on index out of bounds
        "loads",
        # group: might fail depending on state
        "itxn",
        "itxna",
        "itxnas",
        "gitxn",
        "gitxna",
        "gitxnas",
    ]
)

_should_be_empty = PURE_AVM_OPS & IMPURE_SIDE_EFFECT_FREE_AVM_OPS
assert not _should_be_empty, _should_be_empty
SIDE_EFFECT_FREE_AVM_OPS = frozenset([*PURE_AVM_OPS, *IMPURE_SIDE_EFFECT_FREE_AVM_OPS])

COMPILE_TIME_CONSTANT_OPS = frozenset(
    [
        # "generic" comparison ops
        "==",
        "!=",
        # uint64 comparison ops
        "<",
        "<=",
        ">",
        ">=",
        # boolean ops
        "!",
        "&&",
        "||",
        # uint64 bitwise ops
        "&",
        "|",
        "^",
        "~",
        "shl",
        "shr",
        # uint64 math
        "+",
        "-",
        "*",
        "/",
        "%",
        "exp",
        "sqrt",
        # wide math: multi-return - covered by GVN but not here
        "addw",
        "mulw",
        "divw",
        "expw",
        "divmodw",
        # bit/byte ops
        "concat",
        "extract",
        "extract3",
        "getbit",
        "getbyte",
        "len",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "substring",
        "substring3",
        # conversion
        "itob",
        "btoi",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        # byte math
        "b+",
        "b-",
        "b*",
        "b/",
        "b%",
        "bsqrt",
        # byte comaprison ops
        "b==",
        "b!=",
        "b<",
        "b<=",
        "b>",
        "b>=",
        # byte bitwise ops
        "b&",
        "b|",
        "b^",
        "b~",
        # misc
        "bzero",
        "select",
        "bitlen",
        # implemented hash ops
        "keccak256",
        "sha256",
        "sha3_256",
        "sha512_256",
        # ! unimplemented for constant arg evaluation
        "base64_decode",
        "json_ref",
        "ec_add",
        "ec_map_to",
        "ec_multi_scalar_mul",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "falcon_verify",
        "mimc",
        "vrf_verify",
        # AVM vNext ops (currently v13)
        "poseidon2",
        "sha512",
        "sumhash512",
    ]
)

assert COMPILE_TIME_CONSTANT_OPS.issubset(PURE_AVM_OPS), COMPILE_TIME_CONSTANT_OPS - PURE_AVM_OPS


_U64_MASK = (1 << 64) - 1


def fold_addw(a: int, b: int) -> tuple[int, int]:
    total = a + b
    return total >> 64, total & _U64_MASK


def fold_mulw(a: int, b: int) -> tuple[int, int]:
    product = a * b
    return product >> 64, product & _U64_MASK


def fold_expw(a: int, b: int) -> tuple[int, int] | None:
    if a == 0 and b == 0:
        return None  # 0**0 traps on AVM
    result = a**b
    if result.bit_length() > 128:
        return None  # would overflow uint128
    return result >> 64, result & _U64_MASK


def fold_divw(hi: int, lo: int, divisor: int) -> int | None:
    if divisor == 0:
        return None
    dividend = (hi << 64) | lo
    quotient = dividend // divisor
    if not valid_uint64(quotient):
        return None
    return quotient


def fold_divmodw(h1: int, l1: int, h2: int, l2: int) -> tuple[int, int, int, int] | None:
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


EXTRACT_UINTN_BYTE_SIZE: typing.Final[Mapping[AVMOp, int]] = {
    AVMOp.extract_uint16: 2,
    AVMOp.extract_uint32: 4,
    AVMOp.extract_uint64: 8,
}


def fold_extract_uint_n(op: AVMOp, b: bytes, offset: int) -> int | None:
    byte_size = EXTRACT_UINTN_BYTE_SIZE.get(op)
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


def choose_encoding(
    a: AVMBytesEncoding, b: AVMBytesEncoding, *, is_concat: bool = False
) -> AVMBytesEncoding:
    if a == b:
        # special case handling of utf8:
        # most byte/bit ops. would destroy
        # encoding save for concat
        match a:
            case AVMBytesEncoding.utf8:
                return a if is_concat else AVMBytesEncoding.unknown
            case _:
                # preserve encoding if both equal
                return a
    # exclude utf8 from known choices, we don't preserve that encoding choice unless
    # they're both utf8 strings and the op. is a concat, which is covered by the first check
    known_binary_choices = {a, b} - {AVMBytesEncoding.utf8, AVMBytesEncoding.unknown}
    if not known_binary_choices:
        return AVMBytesEncoding.unknown

    # pick the most compact encoding of the known binary encodings
    if AVMBytesEncoding.base64 in known_binary_choices:
        return AVMBytesEncoding.base64
    if AVMBytesEncoding.base32 in known_binary_choices:
        return AVMBytesEncoding.base32
    return AVMBytesEncoding.base16


def chop_encoding(enc: AVMBytesEncoding) -> AVMBytesEncoding:
    """When a bytes operation might not respect code-point boundaries,
    don't keep UTF-8 encoding."""
    return AVMBytesEncoding.unknown if enc == AVMBytesEncoding.utf8 else enc
