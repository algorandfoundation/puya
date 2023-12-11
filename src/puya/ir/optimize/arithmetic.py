import operator
from collections.abc import Callable
from itertools import zip_longest

import attrs
import structlog

from puya.avm_type import AVMType
from puya.codegen.utils import format_bytes
from puya.context import CompileContext
from puya.errors import CodeError
from puya.ir import models
from puya.ir.avm_ops import AVMOp

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def get_int_constant(value: models.ValueProvider) -> int | None:
    if isinstance(value, models.UInt64Constant):
        return value.value
    return None


def get_biguint_constant(value: models.ValueProvider) -> int | None:
    if isinstance(value, models.BigUIntConstant):
        return value.value
    return None


def byte_wise(op: Callable[[int, int], int], lhs: bytes, rhs: bytes) -> bytes:
    return bytes([op(a, b) for a, b in zip_longest(lhs[::-1], rhs[::-1], fillvalue=0)][::-1])


def try_simplify_arithmetic_ops(value: models.ValueProvider) -> models.ValueProvider | None:
    # TODO: handle bytes math
    # TODO: handle all math ops including shl, shr, exp, etc
    match value:
        case models.Intrinsic(
            args=[models.UInt64Constant(value=x)],
            op=(AVMOp.not_ | AVMOp.bitwise_not) as unary_uint64_op,
            source_location=op_loc,
        ):
            if unary_uint64_op == AVMOp.not_:
                not_x = models.UInt64Constant(source_location=op_loc, value=0 if x else 1)
                logger.debug(f"Folded !{x} to {not_x}")
            else:
                not_x = models.UInt64Constant(source_location=op_loc, value=x ^ 0xFFFFFFFFFFFFFFFF)
                logger.debug(f"Folded ~{x} to {not_x}")
            return not_x
        case models.Intrinsic(
            args=[models.BytesConstant(value=bites, encoding=encoding)],
            op=AVMOp.bitwise_not_bytes,
            source_location=op_loc,
        ):
            not_bites = models.BytesConstant(
                source_location=op_loc, value=bytes([x ^ 0xFF for x in bites]), encoding=encoding
            )
            logger.debug(f"Folded ~{bites!r} to {not_bites.value!r}")
            return not_bites
        case models.Intrinsic(
            op=AVMOp.len_,
            args=[models.BytesConstant(value=x, encoding=encoding)],
            source_location=op_loc,
        ):
            len_x = len(x)
            logger.debug(f"Folded len({format_bytes(x, encoding)}) to {len_x}")
            return models.UInt64Constant(source_location=op_loc, value=len_x)
        case models.Intrinsic(
            op=AVMOp.setbit,
            args=[
                models.BytesConstant() as byte_const,
                models.UInt64Constant() as index,
                models.UInt64Constant() as value,
            ],
            source_location=op_loc,
        ):
            binary_array = [
                x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
            ]
            binary_array[index.value] = "1" if value.value else "0"
            binary_string = "".join(binary_array)
            adjusted_const_value = int(binary_string, 2).to_bytes(
                len(byte_const.value), byteorder="big"
            )
            return models.BytesConstant(
                source_location=op_loc, encoding=byte_const.encoding, value=adjusted_const_value
            )
        case models.Intrinsic(
            op=AVMOp.getbit,
            args=[
                models.BytesConstant() as byte_const,
                models.UInt64Constant() as index,
            ],
            source_location=op_loc,
        ):
            binary_array = [
                x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
            ]
            the_bit = binary_array[index.value]
            return models.UInt64Constant(source_location=op_loc, value=int(the_bit))
        case models.Intrinsic(
            op=AVMOp.extract | AVMOp.extract3,
            immediates=[int(S), int(L)],
            args=[models.BytesConstant(value=A, encoding=encoding)],
            source_location=op_loc,
        ) | models.Intrinsic(
            op=AVMOp.extract | AVMOp.extract3,
            immediates=[],
            args=[
                models.BytesConstant(value=A, encoding=encoding),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=L),
            ],
            source_location=op_loc,
        ):
            if L == 0:
                extracted = A[S:]
            else:
                extracted = A[S : S + L]
            return models.BytesConstant(source_location=op_loc, encoding=encoding, value=extracted)
        case models.Intrinsic(
            op=AVMOp.substring | AVMOp.substring3,
            immediates=[int(S), int(E)],
            args=[models.BytesConstant(value=A, encoding=encoding)],
            source_location=op_loc,
        ) | models.Intrinsic(
            op=AVMOp.substring | AVMOp.substring3,
            immediates=[],
            args=[
                models.BytesConstant(value=A, encoding=encoding),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=E),
            ],
            source_location=op_loc,
        ):
            if E < S:
                raise CodeError("substring would fail at runtime", op_loc)
            extracted = A[S:E]
            return models.BytesConstant(source_location=op_loc, encoding=encoding, value=extracted)
        case models.Intrinsic(
            op=AVMOp.concat,
            args=[models.Value(atype=AVMType.bytes) as ba, models.BytesConstant(value=b"")],
        ):
            return ba
        case models.Intrinsic(
            op=AVMOp.concat,
            args=[models.BytesConstant(value=b""), models.Value(atype=AVMType.bytes) as bb],
        ):
            return bb
        case models.Intrinsic(
            op=(
                AVMOp.concat
                | AVMOp.eq
                | AVMOp.neq
                | AVMOp.bitwise_and_bytes
                | AVMOp.bitwise_or_bytes
                | AVMOp.bitwise_xor_bytes
            ) as bytes_op,
            args=[
                models.BytesConstant(value=a, encoding=encoding_a),
                models.BytesConstant(value=b, encoding=encoding_b),
            ],
            source_location=op_loc,
        ):
            if bytes_op == AVMOp.concat:
                if encoding_a == encoding_b:
                    a_b = a + b
                    logger.debug(
                        f"Folded concat({format_bytes(a, encoding_a)},"
                        f" {format_bytes(b, encoding_b)}) to {a_b!r}"
                    )
                    return models.BytesConstant(
                        source_location=op_loc, value=a_b, encoding=encoding_a
                    )
            elif bytes_op == AVMOp.eq:
                return models.UInt64Constant(value=int(a == b), source_location=op_loc)
            elif bytes_op == AVMOp.neq:
                return models.UInt64Constant(value=int(a != b), source_location=op_loc)
            else:
                do_op = {
                    AVMOp.bitwise_and_bytes: operator.and_,
                    AVMOp.bitwise_or_bytes: operator.or_,
                    AVMOp.bitwise_xor_bytes: operator.xor,
                }[bytes_op]
                return models.BytesConstant(
                    value=byte_wise(do_op, a, b), encoding=encoding_a, source_location=op_loc
                )
        case models.Intrinsic(
            args=[
                models.Value(atype=AVMType.uint64) as a,
                models.Value(atype=AVMType.uint64) as b,
            ],
            op=op,
        ):
            c: int | models.Value | None = None
            a_const = get_int_constant(a)
            b_const = get_int_constant(b)
            if a == b:
                match op:
                    case AVMOp.sub:
                        c = 0
                    case AVMOp.eq | AVMOp.lte | AVMOp.gte:
                        c = 1
                    case AVMOp.neq:
                        c = 0
                    case AVMOp.div_floor:
                        c = 1
                    case AVMOp.bitwise_xor:
                        c = 0
                    case AVMOp.bitwise_and | AVMOp.bitwise_or:
                        c = a
            # 0 == b <-> !b
            elif a_const == 0 and op == AVMOp.eq:
                return attrs.evolve(value, op=AVMOp.not_, args=[b])
            # a == 0 <-> !a
            elif b_const == 0 and op == AVMOp.eq:
                return attrs.evolve(value, op=AVMOp.not_, args=[a])
            # TODO: can we somehow do the below only in a boolean context?
            # # 0 != b <-> b
            # elif a_const == 0 and op == AVMOp.neq:
            #     c = b
            # # a != 0 <-> a
            # elif b_const == 0 and op == AVMOp.neq:
            #     c = a
            elif a_const == 1 and op == AVMOp.mul:
                c = b
            elif b_const == 1 and op == AVMOp.mul:
                c = a
            elif a_const == 0 and op in (AVMOp.add, AVMOp.or_):
                c = b
            elif b_const == 0 and op in (AVMOp.add, AVMOp.sub, AVMOp.or_):
                c = a
            elif 0 in (a_const, b_const) and op in (AVMOp.mul, AVMOp.and_):
                c = 0
            elif a_const is not None and b_const is not None:
                match op:
                    case AVMOp.add:
                        c = a_const + b_const
                    case AVMOp.sub:
                        c = a_const - b_const
                    case AVMOp.mul:
                        c = a_const * b_const
                    case AVMOp.div_floor:
                        c = a_const // b_const
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
                        c = int(a_const and b_const)
                    case AVMOp.or_:
                        c = int(a_const or b_const)
                    case AVMOp.shl:
                        c = (a_const << b_const) % (2**64)
                    case AVMOp.shr:
                        c = a_const >> b_const
                    case AVMOp.exp:
                        if a_const == 0 and b_const == 0:
                            raise CodeError("exp would fail at runtime", value.source_location)
                        c = a_const**b_const
                    case AVMOp.bitwise_or:
                        c = a_const | b_const
                    case AVMOp.bitwise_and:
                        c = a_const & b_const
                    case AVMOp.bitwise_xor:
                        c = a_const ^ b_const
            if c is not None:
                if isinstance(c, models.ValueProvider):
                    logger.debug(f"Folded {a} {op} {b} to {c}")
                    return c
                else:
                    if c < 0:
                        # Value cannot be folded as it would result in a negative uint
                        return None
                    logger.debug(f"Folded {a_const} {op} {b_const} to {c}")
                    return models.UInt64Constant(value=c, source_location=value.source_location)
        case models.Intrinsic(
            args=[
                models.Value(atype=AVMType.bytes) as a,
                models.Value(atype=AVMType.bytes) as b,
            ],
            op=op,
        ):
            c = None
            a_const = get_biguint_constant(a)
            b_const = get_biguint_constant(b)
            if a == b:
                match op:
                    case AVMOp.sub_bytes:
                        c = 0
                    case AVMOp.eq_bytes | AVMOp.eq:
                        c = 1
                    case AVMOp.neq_bytes | AVMOp.neq:
                        c = 0
                    case AVMOp.div_floor_bytes:
                        c = 1
            elif a_const == 1 and op == AVMOp.mul_bytes:
                c = b
            elif b_const == 1 and op == AVMOp.mul_bytes:
                c = a
            elif a_const == 0 and op == AVMOp.add_bytes:
                c = b
            elif b_const == 0 and op in (AVMOp.add_bytes, AVMOp.sub_bytes):
                c = a
            elif 0 in (a_const, b_const) and op == AVMOp.mul_bytes:
                c = 0
            elif a_const is not None and b_const is not None:
                match op:
                    case AVMOp.add_bytes:
                        c = a_const + b_const
                    case AVMOp.sub_bytes:
                        c = a_const - b_const
                    case AVMOp.mul_bytes:
                        c = a_const * b_const
                    case AVMOp.div_floor_bytes:
                        c = a_const // b_const
                    case AVMOp.lt_bytes:
                        c = 1 if a_const < b_const else 0
                    case AVMOp.lte_bytes:
                        c = 1 if a_const <= b_const else 0
                    case AVMOp.gt_bytes:
                        c = 1 if a_const > b_const else 0
                    case AVMOp.gte_bytes:
                        c = 1 if a_const >= b_const else 0
                    case AVMOp.eq_bytes | AVMOp.eq:
                        c = 1 if a_const == b_const else 0
                    case AVMOp.neq_bytes | AVMOp.neq:
                        c = 1 if a_const != b_const else 0
            if c is not None:
                if isinstance(c, models.ValueProvider):
                    logger.debug(f"Folded {a} {op} {b} to {c}")
                    return c
                logger.debug(f"Folded {a_const} {op} {b_const} to {c}")
                if op in (
                    AVMOp.eq_bytes,
                    AVMOp.eq,
                    AVMOp.neq_bytes,
                    AVMOp.neq,
                    AVMOp.lt_bytes,
                    AVMOp.lte_bytes,
                    AVMOp.gt_bytes,
                    AVMOp.gte_bytes,
                ):
                    return models.UInt64Constant(value=c, source_location=value.source_location)
                else:
                    return models.BigUIntConstant(value=c, source_location=value.source_location)

    return None


def arithmetic_simplification(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Simplify arithmetic expressions e.g. a-a -> 0, a*0 -> 0, a*1 -> a"""
    modified = 0

    for block in subroutine.body:
        for op in block.ops:
            match op:
                case models.Assignment(source=source) as assignment:
                    simplified = try_simplify_arithmetic_ops(source)
                    if simplified is not None:
                        assignment.source = simplified
                        modified += 1

    return modified > 0
