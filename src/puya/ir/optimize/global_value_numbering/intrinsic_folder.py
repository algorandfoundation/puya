"""Constant folding and structural numbering for pure intrinsic ops.

Consumes a pure intrinsic plus its already-numbered operands and returns value
numbers — either by folding to a constant / operand pass-through, or by interning
a canonical structural key. Never numbers operands itself; the operand VNs are
its only window onto them.
"""

import hashlib
import itertools
import math
import operator
import typing
from collections.abc import Callable, Set

import attrs

from puya import algo_constants
from puya.avm import AVMType
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._intrinsics import EXTRACT_UINTN_BYTE_SIZE, choose_encoding, valid_uint64
from puya.ir.optimize.global_value_numbering.tables import (
    VN,
    BytesConstKey,
    ConstKey,
    GVNTables,
    IntrinsicKey,
    ProviderKey,
    UInt64ConstKey,
)
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.utils import sha512_256_hash, symmetric_mapping, unique

__all__ = [
    "IntrinsicFolder",
]

ArgDefs: typing.TypeAlias = list[ConstKey | ProviderKey | None]

# Commutative AVM ops: sorting operand VNs lets us recognise a+b == b+a.
COMMUTATIVE_OPS: typing.Final[Set[AVMOp]] = frozenset(
    [
        AVMOp.add,
        AVMOp.mul,
        AVMOp.eq,
        AVMOp.neq,
        AVMOp.bitwise_and,
        AVMOp.bitwise_or,
        AVMOp.bitwise_xor,
        AVMOp.and_,
        AVMOp.or_,
        AVMOp.addw,
        AVMOp.mulw,
        AVMOp.add_bytes,
        AVMOp.mul_bytes,
        AVMOp.eq_bytes,
        AVMOp.neq_bytes,
        AVMOp.bitwise_and_bytes,
        AVMOp.bitwise_or_bytes,
        AVMOp.bitwise_xor_bytes,
    ]
)

# Ordering ops: sort operand VNs and mirror the predicate, so a<b matches b>a.
MIRROR_OPS: typing.Final = symmetric_mapping(
    (AVMOp.lt, AVMOp.gt),
    (AVMOp.lte, AVMOp.gte),
    (AVMOp.lt_bytes, AVMOp.gt_bytes),
    (AVMOp.lte_bytes, AVMOp.gte_bytes),
)

# Inverse comparisons for negation-aware numbering: !(a < b) == (a >= b).
INVERSE_COMPARISONS: typing.Final = symmetric_mapping(
    (AVMOp.lt, AVMOp.gte),
    (AVMOp.gt, AVMOp.lte),
    (AVMOp.eq, AVMOp.neq),
    (AVMOp.lt_bytes, AVMOp.gte_bytes),
    (AVMOp.gt_bytes, AVMOp.lte_bytes),
    (AVMOp.eq_bytes, AVMOp.neq_bytes),
)

U64_MASK = (1 << 64) - 1


@attrs.frozen
class IntrinsicFolder:
    _tables: GVNTables

    def number(self, intrinsic: models.Intrinsic, arg_vns: tuple[VN, ...]) -> tuple[VN, ...]:
        """Fold to a constant/pass-through, else assign a structural VN."""
        arg_defs = [self._tables.vn_definition.get(arg_vn) for arg_vn in arg_vns]
        folded = self._const_fold(intrinsic, arg_vns, arg_defs)
        if folded is not None:
            return folded
        return self._number_generic(intrinsic, arg_vns, arg_defs)

    def _number_generic(
        self, intrinsic: models.Intrinsic, arg_vns: tuple[VN, ...], arg_defs: ArgDefs
    ) -> tuple[VN, ...]:
        """Structural numbering for ops that didn't const-fold"""
        op = intrinsic.op
        match arg_vns:
            case [vn1, vn2] if vn1 == vn2:
                match op:
                    case (
                        AVMOp.neq
                        | AVMOp.neq_bytes
                        | AVMOp.lt
                        | AVMOp.lt_bytes
                        | AVMOp.gt
                        | AVMOp.gt_bytes
                    ):
                        return self._tables.const_bool(0)
                    case (
                        AVMOp.bitwise_xor
                        # | AVMOp.bitwise_xor_bytes - need length
                        | AVMOp.sub
                    ):
                        return self._tables.const_uint64(0)
                    case AVMOp.sub_bytes:
                        return self._tables.const_bytes(b"", AVMBytesEncoding.unknown)
                    case (
                        AVMOp.eq
                        | AVMOp.eq_bytes
                        | AVMOp.lte
                        | AVMOp.lte_bytes
                        | AVMOp.gte
                        | AVMOp.gte_bytes
                        # | AVMOp.div_floor - div by zero
                        # | AVMOp.div_floor_bytes - div by zero
                    ):
                        return self._tables.const_bool(1)
                    case (
                        AVMOp.bitwise_and
                        | AVMOp.bitwise_and_bytes
                        | AVMOp.bitwise_or
                        | AVMOp.bitwise_or_bytes
                    ):
                        return (vn1,)

        # One-const algebraic simplifications
        if len(arg_defs) == 2:
            a_def, b_def = arg_defs
            # refuse to simplify if both are consts but didn't fold,
            # likely this is due to it being guaranteed to fail
            if isinstance(a_def, ConstKey) != isinstance(b_def, ConstKey):
                # make sure they're backed by the same AVMType, otherwise we
                # must refuse to fold e.g. == or !=
                match unique(arg.ir_type.maybe_avm_type for arg in intrinsic.args):
                    case [AVMType.uint64]:
                        a_const = a_def.value if isinstance(a_def, UInt64ConstKey) else None
                        b_const = b_def.value if isinstance(b_def, UInt64ConstKey) else None
                        result = self._fold_uint64_binary_op_one_const(
                            op, intrinsic, arg_vns, a_const, b_const
                        )
                        if result is not None:
                            return result
                    case [AVMType.bytes]:
                        a_bg = a_def.as_biguint if isinstance(a_def, BytesConstKey) else None
                        b_bg = b_def.as_biguint if isinstance(b_def, BytesConstKey) else None
                        # secondary guard in case an operand is oversized
                        if (a_bg is None) != (b_bg is None):
                            result = self._fold_bytes_binary_op_one_const(op, arg_vns, a_bg, b_bg)
                            if result is not None:
                                return result

        if op in COMMUTATIVE_OPS:
            arg_vns = tuple(sorted(arg_vns))
        elif op in MIRROR_OPS and arg_vns[0] > arg_vns[1]:
            arg_vns = (arg_vns[1], arg_vns[0])
            op = MIRROR_OPS[op]
        key = IntrinsicKey(op=op, immediates=tuple(intrinsic.immediates), arg_vns=arg_vns)
        return self._tables.lookup_or_assign_vp(key, intrinsic)

    def _const_fold(
        self, intrinsic: models.Intrinsic, arg_vns: tuple[VN, ...], arg_defs: ArgDefs
    ) -> tuple[VN, ...] | None:
        """Fold the op to a constant or operand pass-through; None if it can't."""
        match intrinsic.op:
            # -- uint64 binary arithmetic / comparison / bitwise / logical --
            case AVMOp.add:
                return self._fold_u64_binary(arg_defs, operator.add)
            case AVMOp.sub:
                return self._fold_u64_binary(arg_defs, operator.sub)
            case AVMOp.mul:
                return self._fold_u64_binary(arg_defs, operator.mul)
            case AVMOp.div_floor:
                return self._fold_u64_binary(arg_defs, lambda x, y: None if y == 0 else x // y)
            case AVMOp.mod:
                return self._fold_u64_binary(arg_defs, lambda x, y: None if y == 0 else x % y)
            case AVMOp.lt:
                return self._fold_u64_binary_bool(arg_defs, operator.lt)
            case AVMOp.lte:
                return self._fold_u64_binary_bool(arg_defs, operator.le)
            case AVMOp.gt:
                return self._fold_u64_binary_bool(arg_defs, operator.gt)
            case AVMOp.gte:
                return self._fold_u64_binary_bool(arg_defs, operator.ge)
            case AVMOp.and_:
                return self._fold_u64_binary_bool(arg_defs, lambda x, y: x and y)
            case AVMOp.or_:
                return self._fold_u64_binary_bool(arg_defs, lambda x, y: x or y)
            case AVMOp.shl:
                return self._fold_u64_binary(
                    arg_defs, lambda x, y: None if y >= 64 else (x << y) % (2**64)
                )
            case AVMOp.shr:
                return self._fold_u64_binary(arg_defs, lambda x, y: None if y >= 64 else x >> y)
            case AVMOp.exp:
                return self._fold_u64_binary(
                    arg_defs, lambda x, y: None if (x == 0 and y == 0) else x**y
                )
            case AVMOp.bitwise_or:
                return self._fold_u64_binary(arg_defs, operator.or_)
            case AVMOp.bitwise_and:
                return self._fold_u64_binary(arg_defs, operator.and_)
            case AVMOp.bitwise_xor:
                return self._fold_u64_binary(arg_defs, operator.xor)
            # -- (in)equality: operands may be uint64 or raw bytes --
            case AVMOp.eq:
                match arg_defs:
                    case [UInt64ConstKey(value=x), UInt64ConstKey(value=y)]:
                        return self._tables.const_bool(x == y)
                    case [BytesConstKey(value=xb), BytesConstKey(value=yb)]:
                        return self._tables.const_bool(xb == yb)
            case AVMOp.neq:
                match arg_defs:
                    case [UInt64ConstKey(value=x), UInt64ConstKey(value=y)]:
                        return self._tables.const_bool(x != y)
                    case [BytesConstKey(value=xb), BytesConstKey(value=yb)]:
                        return self._tables.const_bool(xb != yb)
            case AVMOp.getbit:
                match arg_defs:
                    case [UInt64ConstKey(value=source), UInt64ConstKey(value=index)]:
                        if index < 64:
                            bit_value = source & (1 << index)
                            return self._tables.const_bool(bit_value)
                    case [BytesConstKey(value=bv), UInt64ConstKey(value=index)]:
                        if index < len(bv) * 8:
                            byte_index, bit_offset = divmod(index, 8)
                            bit_value = (bv[byte_index] >> (7 - bit_offset)) & 1
                            return self._tables.const_bool(bit_value)
            # -- biguint binary (bytes operands interpreted as big-endian biguints) --
            case AVMOp.add_bytes:
                return self._fold_biguint_binary(arg_defs, operator.add)
            case AVMOp.sub_bytes:
                return self._fold_biguint_binary(arg_defs, operator.sub)
            case AVMOp.mul_bytes:
                return self._fold_biguint_binary(arg_defs, operator.mul)
            case AVMOp.div_floor_bytes:
                return self._fold_biguint_binary(arg_defs, lambda x, y: None if y == 0 else x // y)
            case AVMOp.mod_bytes:
                return self._fold_biguint_binary(arg_defs, lambda x, y: None if y == 0 else x % y)
            case AVMOp.lt_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.lt)
            case AVMOp.lte_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.le)
            case AVMOp.gt_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.gt)
            case AVMOp.gte_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.ge)
            case AVMOp.eq_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.eq)
            case AVMOp.neq_bytes:
                return self._fold_biguint_binary_bool(arg_defs, operator.ne)
            # -- byte-wise bitwise --
            case AVMOp.bitwise_or_bytes:
                return self._fold_bytes_bitwise(arg_defs, operator.or_)
            case AVMOp.bitwise_and_bytes:
                return self._fold_bytes_bitwise(arg_defs, operator.and_)
            case AVMOp.bitwise_xor_bytes:
                return self._fold_bytes_bitwise(arg_defs, operator.xor)
            # -- uint64 unary --
            case AVMOp.not_:
                match arg_defs:
                    case [UInt64ConstKey(value=x)]:
                        return self._tables.const_bool(not x)
                    case [IntrinsicKey(op=source_op) as comp]:
                        # !(comparison) -> inverse comparison's key
                        if inverse_op := INVERSE_COMPARISONS.get(source_op):
                            inverse_key = IntrinsicKey(
                                op=inverse_op, immediates=comp.immediates, arg_vns=comp.arg_vns
                            )
                            return self._tables.lookup_or_assign_vp(inverse_key, intrinsic)
            case AVMOp.bitwise_not:
                match arg_defs:
                    case [UInt64ConstKey(value=x)]:
                        inverted = x ^ 0xFFFFFFFFFFFFFFFF
                        return self._tables.const_uint64(inverted)
            case AVMOp.sqrt:
                match arg_defs:
                    case [UInt64ConstKey(value=x)]:
                        return self._tables.const_uint64(math.isqrt(x))
            case AVMOp.bitlen:
                match arg_defs:
                    case [UInt64ConstKey(value=x)]:
                        return self._tables.const_uint64(x.bit_length())
                    case [BytesConstKey(value=bv)]:
                        bytes_as_int = int.from_bytes(bv, byteorder="big", signed=False)
                        return self._tables.const_uint64(bytes_as_int.bit_length())
            # -- bytes unary --
            case AVMOp.bitwise_not_bytes:
                match arg_defs:
                    case [BytesConstKey(value=bv, encoding=enc)]:
                        bitwise_not = bytes(x ^ 0xFF for x in bv)
                        return self._tables.const_bytes(bitwise_not, chop_encoding(enc))
            case AVMOp.btoi:
                match arg_defs:
                    case [BytesConstKey(value=bv)] if len(bv) <= 8:
                        int_value = int.from_bytes(bv, byteorder="big", signed=False)
                        return self._tables.const_uint64(int_value)
                    case [IntrinsicKey(op=AVMOp.itob, arg_vns=[source_vn])]:
                        # btoi(itob(x)) = x
                        return (source_vn,)
            case AVMOp.bsqrt:
                match arg_defs:
                    case [BytesConstKey(as_biguint=int(int_value))]:
                        return self._tables.const_biguint(math.isqrt(int_value))
            # -- hashes --
            case AVMOp.sha256:
                match arg_defs:
                    case [BytesConstKey(value=bv)]:
                        hashed = hashlib.sha256(bv).digest()
                        return self._tables.const_bytes(hashed, AVMBytesEncoding.base16)
            case AVMOp.sha3_256:
                match arg_defs:
                    case [BytesConstKey(value=bv)]:
                        hashed = hashlib.sha3_256(bv).digest()
                        return self._tables.const_bytes(hashed, AVMBytesEncoding.base16)
            case AVMOp.sha512_256:
                match arg_defs:
                    case [BytesConstKey(value=bv)]:
                        hashed = sha512_256_hash(bv)
                        return self._tables.const_bytes(hashed, AVMBytesEncoding.base16)
            case AVMOp.keccak256:
                match arg_defs:
                    case [BytesConstKey(value=bv)]:
                        from Cryptodome.Hash import keccak

                        hashed = keccak.new(data=bv, digest_bits=256).digest()
                        return self._tables.const_bytes(hashed, AVMBytesEncoding.base16)
            # -- length / conversion / fill --
            case AVMOp.len_:
                match arg_defs:
                    case [BytesConstKey(value=len_arg)]:
                        len_result = len(len_arg)
                        if len_result <= algo_constants.MAX_BYTES_LENGTH:
                            return self._tables.const_uint64(len(len_arg))
            case AVMOp.itob:
                match arg_defs:
                    case [UInt64ConstKey(value=itob_arg)]:
                        if valid_uint64(itob_arg):
                            folded_bytes = itob_arg.to_bytes(8, byteorder="big", signed=False)
                            return self._tables.const_bytes(folded_bytes, AVMBytesEncoding.base16)
            case AVMOp.bzero:
                match arg_defs:
                    case [UInt64ConstKey(value=bzero_arg)]:
                        if bzero_arg <= algo_constants.MAX_BYTES_LENGTH:
                            folded_bytes = b"\x00" * bzero_arg
                            return self._tables.const_bytes(folded_bytes, AVMBytesEncoding.base16)
            # -- bit / byte get & set --
            case AVMOp.setbit:
                match arg_defs:
                    case [
                        UInt64ConstKey(value=source),
                        UInt64ConstKey(value=index),
                        UInt64ConstKey(value=value),
                    ]:
                        if index < 64:
                            if value:
                                folded = source | (1 << index)
                            else:
                                folded = source & ~(1 << index)
                            return self._tables.const_uint64(folded)
                    case [
                        BytesConstKey(value=bv, encoding=enc),
                        UInt64ConstKey(value=index),
                        UInt64ConstKey(value=value),
                    ]:
                        if index < len(bv) * 8:
                            byte_index, bit_offset = divmod(index, 8)
                            mask = 1 << (7 - bit_offset)
                            byte = bv[byte_index]
                            new_byte = byte | mask if value else byte & ~mask
                            folded_bytes = (
                                bv[:byte_index] + bytes([new_byte]) + bv[byte_index + 1 :]
                            )
                            return self._tables.const_bytes(folded_bytes, chop_encoding(enc))
            case AVMOp.setbyte:
                match arg_defs:
                    case [
                        BytesConstKey(value=bv, encoding=enc),
                        UInt64ConstKey(value=index),
                        UInt64ConstKey(value=value),
                    ]:
                        if index < len(bv) and value <= 0xFF:
                            out = bytearray(bv)
                            out[index] = value
                            return self._tables.const_bytes(bytes(out), chop_encoding(enc))
            case AVMOp.getbyte:
                match arg_defs:
                    case [BytesConstKey(value=bv), UInt64ConstKey(value=index)]:
                        if index < len(bv):
                            return self._tables.const_uint64(bv[index])
            # -- select --
            case AVMOp.select:
                # arg layout: [false_branch, true_branch, selector]
                if arg_vns[0] == arg_vns[1]:
                    # select(x, x, _) → x
                    return (arg_vns[0],)
                if isinstance(arg_defs[2], UInt64ConstKey):
                    # const selector → pick branch directly
                    return (arg_vns[1] if arg_defs[2].value else arg_vns[0],)
            # -- slicing / replacement --
            case AVMOp.replace2:
                match arg_defs, intrinsic.immediates:
                    case [
                        [
                            BytesConstKey(value=src_bytes, encoding=src_enc),
                            BytesConstKey(value=repl_bytes, encoding=repl_enc),
                        ],
                        [int(start)],
                    ]:
                        return self._fold_replace(src_bytes, start, repl_bytes, src_enc, repl_enc)
            case AVMOp.replace3:
                match arg_defs:
                    case [
                        BytesConstKey(value=src_bytes, encoding=src_enc),
                        UInt64ConstKey(value=start),
                        BytesConstKey(value=repl_bytes, encoding=repl_enc),
                    ]:
                        return self._fold_replace(src_bytes, start, repl_bytes, src_enc, repl_enc)
            case AVMOp.concat:
                match arg_defs:
                    case [
                        BytesConstKey(value=first_byte_const, encoding=first_enc),
                        BytesConstKey(value=second_byte_const, encoding=second_enc),
                    ]:
                        concat_result = first_byte_const + second_byte_const
                        if len(concat_result) <= algo_constants.MAX_BYTES_LENGTH:
                            return self._tables.const_bytes(
                                concat_result,
                                choose_encoding(first_enc, second_enc, is_concat=True),
                            )
                    case [BytesConstKey(value=b""), _]:
                        # concat(b"", x) → x
                        return (arg_vns[1],)
                    case [_, BytesConstKey(value=b"")]:
                        # concat(x, b"") → x
                        return (arg_vns[0],)
            case AVMOp.substring3:
                match arg_defs:
                    case [
                        BytesConstKey(value=byte_arg, encoding=byte_enc),
                        UInt64ConstKey(value=start_arg),
                        UInt64ConstKey(value=end_arg),
                    ]:
                        return self._fold_substring(byte_arg, start_arg, end_arg, byte_enc)
            case AVMOp.substring:
                match arg_defs, intrinsic.immediates:
                    case [
                        [BytesConstKey(value=byte_arg, encoding=byte_enc)],
                        [int(start_arg), int(end_arg)],
                    ]:
                        return self._fold_substring(byte_arg, start_arg, end_arg, byte_enc)
            case AVMOp.extract3:
                match arg_defs:
                    case [
                        BytesConstKey(value=byte_arg, encoding=byte_enc),
                        UInt64ConstKey(value=start_arg),
                        UInt64ConstKey(value=length_arg),
                    ]:
                        end_arg = start_arg + length_arg
                        if end_arg <= len(byte_arg) <= algo_constants.MAX_BYTES_LENGTH:
                            extract_result = byte_arg[start_arg:end_arg]
                            return self._tables.const_bytes(
                                extract_result, chop_encoding(byte_enc)
                            )
            case AVMOp.extract:
                match arg_defs, intrinsic.immediates:
                    case [
                        [BytesConstKey(value=byte_arg, encoding=byte_enc)],
                        [int(start_arg), int(length_arg)],
                    ]:
                        # immediate variant: L=0 means "extract to end".
                        byte_len = len(byte_arg)
                        end_arg = byte_len if length_arg == 0 else start_arg + length_arg
                        if start_arg <= end_arg <= byte_len <= algo_constants.MAX_BYTES_LENGTH:
                            extract_result = byte_arg[start_arg:end_arg]
                            return self._tables.const_bytes(
                                extract_result, chop_encoding(byte_enc)
                            )
            case AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64 as op:
                match arg_defs:
                    case [BytesConstKey(value=bv), UInt64ConstKey(value=offset)]:
                        byte_size = EXTRACT_UINTN_BYTE_SIZE[op]
                        extracted = bv[offset : offset + byte_size]
                        if len(extracted) == byte_size:
                            bytes_int = int.from_bytes(extracted, byteorder="big", signed=False)
                            return self._tables.const_uint64(bytes_int)
            # -- wide math (multiple results) --
            case AVMOp.addw:
                match arg_defs:
                    case [UInt64ConstKey(value=addw_a), UInt64ConstKey(value=addw_b)]:
                        total = addw_a + addw_b
                        return self._const_wide_math_result((total >> 64, total & U64_MASK))
            case AVMOp.mulw:
                match arg_defs:
                    case [UInt64ConstKey(value=mulw_a), UInt64ConstKey(value=mulw_b)]:
                        product = mulw_a * mulw_b
                        return self._const_wide_math_result((product >> 64, product & U64_MASK))
            case AVMOp.expw:
                match arg_defs:
                    case [UInt64ConstKey(value=expw_a), UInt64ConstKey(value=expw_b)]:
                        if not (expw_a == 0 and expw_b == 0):  # 0**0 traps on AVM
                            expw_result = expw_a**expw_b
                            if expw_result.bit_length() <= 128:
                                return self._const_wide_math_result(
                                    (expw_result >> 64, expw_result & U64_MASK)
                                )
            case AVMOp.divw:
                match arg_defs:
                    case [
                        UInt64ConstKey(value=hi),
                        UInt64ConstKey(value=lo),
                        UInt64ConstKey(value=divisor),
                    ]:
                        if divisor != 0:
                            dividend = (hi << 64) | lo
                            quotient = dividend // divisor
                            if valid_uint64(quotient):
                                return self._tables.const_uint64(quotient)
            case AVMOp.divmodw:
                match arg_defs:
                    case [
                        UInt64ConstKey(value=h1),
                        UInt64ConstKey(value=l1),
                        UInt64ConstKey(value=h2),
                        UInt64ConstKey(value=l2),
                    ]:
                        divmodw_divisor = (h2 << 64) | l2
                        if divmodw_divisor != 0:
                            divmodw_dividend = (h1 << 64) | l1
                            q, r = divmod(divmodw_dividend, divmodw_divisor)
                            return self._const_wide_math_result(
                                (q >> 64, q & U64_MASK, r >> 64, r & U64_MASK)
                            )
        return None

    def _const_wide_math_result(self, values: tuple[int, ...]) -> tuple[VN, ...]:
        return tuple(vn for val in values for vn in self._tables.const_uint64(val))

    def _fold_u64_binary(
        self, arg_defs: ArgDefs, compute: Callable[[int, int], int | None]
    ) -> tuple[VN, ...] | None:
        """Fold a uint64 binary op over two uint64 constants. `compute` returns None if
        the op would trap (e.g. div-by-zero); out-of-range results are rejected too."""
        match arg_defs:
            case [UInt64ConstKey(value=x), UInt64ConstKey(value=y)]:
                c = compute(x, y)
                if c is not None and valid_uint64(c):
                    return self._tables.const_uint64(c)
        return None

    def _fold_u64_binary_bool(
        self, arg_defs: ArgDefs, compute: Callable[[int, int], int]
    ) -> tuple[VN, ...] | None:
        match arg_defs:
            case [UInt64ConstKey(value=x), UInt64ConstKey(value=y)]:
                return self._tables.const_bool(compute(x, y))
        return None

    def _fold_biguint_binary(
        self, arg_defs: ArgDefs, compute: Callable[[int, int], int | None]
    ) -> tuple[VN, ...] | None:
        """Fold a biguint binary op over two bytes constants.
        `compute` returns None on trap or a negative on underflow."""
        match arg_defs:
            case [BytesConstKey(as_biguint=int(x)), BytesConstKey(as_biguint=int(y))]:
                c = compute(x, y)
                if c is not None and c >= 0:
                    return self._tables.const_biguint(c)
        return None

    def _fold_biguint_binary_bool(
        self, arg_defs: ArgDefs, compute: Callable[[int, int], int]
    ) -> tuple[VN, ...] | None:
        match arg_defs:
            case [BytesConstKey(as_biguint=int(x)), BytesConstKey(as_biguint=int(y))]:
                c = compute(x, y)
                return self._tables.const_bool(c)
        return None

    def _fold_bytes_bitwise(
        self, arg_defs: ArgDefs, op_fn: Callable[[int, int], int]
    ) -> tuple[VN, ...] | None:
        match arg_defs:
            case [BytesConstKey(value=a, encoding=ea), BytesConstKey(value=b, encoding=eb)]:
                folded = bytes(
                    [
                        op_fn(a1, b1)
                        for a1, b1 in itertools.zip_longest(a[::-1], b[::-1], fillvalue=0)
                    ][::-1]
                )
                return self._tables.const_bytes(folded, choose_encoding(ea, eb))
        return None

    def _fold_uint64_binary_op_one_const(
        self,
        op: AVMOp,
        intrinsic: models.Intrinsic,
        arg_vns: tuple[VN, ...],
        a_const: int | None,
        b_const: int | None,
    ) -> tuple[VN, ...] | None:
        """One-const algebra for uint64 binary ops in a value context: an operand is only
        "bool safe" when its IR type is bool (e.g. `a >= 1` -> `a` only for bool `a`).
        Returns a materialised constant, a pass-through operand's VNs, or None."""

        def bool_safe(arg: models.Value) -> bool:
            return arg.ir_type == PrimitiveIRType.bool

        a, b = intrinsic.args
        vn_a, vn_b = arg_vns
        match op:
            case AVMOp.gte:
                # a >= 0 <-> 1
                if b_const == 0:
                    return self._tables.const_bool(1)
                # a >= 1 <-> a (when a is a bool)
                if b_const == 1 and bool_safe(a):
                    return (vn_a,)
            case AVMOp.lte:
                # 0 <= b <-> 1
                if a_const == 0:
                    return self._tables.const_bool(1)
                # 1 <= b <-> b (when b is a bool)
                if a_const == 1 and bool_safe(b):
                    return (vn_b,)
            case AVMOp.mul:
                if a_const == 1:
                    return (vn_b,)
                if b_const == 1:
                    return (vn_a,)
                if 0 in (a_const, b_const):
                    return self._tables.const_uint64(0)
            case AVMOp.div_floor:
                if b_const == 1:
                    return (vn_a,)
            case AVMOp.mod:
                if b_const == 1:
                    return self._tables.const_uint64(0)
            case AVMOp.add:
                if a_const == 0:
                    return (vn_b,)
                if b_const == 0:
                    return (vn_a,)
            case AVMOp.sub:
                if b_const == 0:
                    return (vn_a,)
            case AVMOp.and_:
                if 0 in (a_const, b_const):
                    return self._tables.const_bool(0)
            case AVMOp.eq:
                if a_const == 0:
                    not_key = IntrinsicKey(op=AVMOp.not_, immediates=(), arg_vns=(vn_b,))
                    return self._tables.lookup_or_assign_vp(not_key, intrinsic)
                if b_const == 0:
                    not_key = IntrinsicKey(op=AVMOp.not_, immediates=(), arg_vns=(vn_a,))
                    return self._tables.lookup_or_assign_vp(not_key, intrinsic)
            case AVMOp.neq:
                # 0 != b <-> b  /  a != 0 <-> a (when the surviving operand is a bool)
                if a_const == 0 and bool_safe(b):
                    return (vn_b,)
                if b_const == 0 and bool_safe(a):
                    return (vn_a,)
            case AVMOp.lt:
                # 0 < b <-> b (when b is a bool)
                if a_const == 0 and bool_safe(b):
                    return (vn_b,)
                # a < 0 <-> 0
                if b_const == 0:
                    return self._tables.const_bool(0)
            case AVMOp.gt:
                # a > 0 <-> a (when a is a bool)
                if b_const == 0 and bool_safe(a):
                    return (vn_a,)
                # 0 > b <-> 0
                if a_const == 0:
                    return self._tables.const_bool(0)
        return None

    def _fold_bytes_binary_op_one_const(
        self, op: AVMOp, arg_vns: tuple[VN, ...], a_const: int | None, b_const: int | None
    ) -> tuple[VN, ...] | None:
        vn_a, vn_b = arg_vns
        match op:
            case AVMOp.mul_bytes:
                if a_const == 1:
                    return (vn_b,)
                if b_const == 1:
                    return (vn_a,)
                if 0 in (a_const, b_const):
                    return self._tables.const_biguint(0)
            case AVMOp.add_bytes:
                if a_const == 0:
                    return (vn_b,)
                if b_const == 0:
                    return (vn_a,)
            case AVMOp.sub_bytes:
                if b_const == 0:
                    return (vn_a,)
            case AVMOp.div_floor_bytes:
                if b_const == 1:
                    return (vn_a,)
            case AVMOp.mod_bytes:
                if b_const == 1:
                    return self._tables.const_biguint(0)
        return None

    def _fold_replace(
        self,
        source: bytes,
        start: int,
        replacement: bytes,
        src_enc: AVMBytesEncoding,
        repl_enc: AVMBytesEncoding,
    ) -> tuple[VN, ...] | None:
        if start + len(replacement) > len(source):
            return None
        out = bytearray(source)
        out[start : start + len(replacement)] = replacement
        return self._tables.const_bytes(bytes(out), choose_encoding(src_enc, repl_enc))

    def _fold_substring(
        self, byte_arg: bytes, start_arg: int, end_arg: int, byte_enc: AVMBytesEncoding
    ) -> tuple[VN, ...] | None:
        if start_arg <= end_arg <= len(byte_arg) <= algo_constants.MAX_BYTES_LENGTH:
            substring_result = byte_arg[start_arg:end_arg]
            return self._tables.const_bytes(substring_result, chop_encoding(byte_enc))
        return None


def chop_encoding(enc: AVMBytesEncoding) -> AVMBytesEncoding:
    """When a bytes operation might not respect code-point boundaries,
    don't keep UTF-8 encoding."""
    return AVMBytesEncoding.unknown if enc == AVMBytesEncoding.utf8 else enc
