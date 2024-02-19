import operator
from collections.abc import Callable
from itertools import zip_longest

import attrs
import structlog

from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import get_definition
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.utils import format_bytes
from puya.utils import itob_eval

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def get_int_constant(value: models.ValueProvider) -> int | None:
    if isinstance(value, models.UInt64Constant):
        return value.value
    return None


def get_biguint_constant(value: models.ValueProvider) -> int | None:
    if isinstance(value, models.BigUIntConstant):
        return value.value
    if isinstance(value, models.BytesConstant) and len(value.value) <= 64:
        return int.from_bytes(value.value, byteorder="big", signed=False)
    return None


def byte_wise(op: Callable[[int, int], int], lhs: bytes, rhs: bytes) -> bytes:
    return bytes([op(a, b) for a, b in zip_longest(lhs[::-1], rhs[::-1], fillvalue=0)][::-1])


def get_byte_constant(
    subroutine: models.Subroutine, byte_arg: models.Value
) -> models.BytesConstant | None:
    if isinstance(byte_arg, models.BytesConstant):
        return byte_arg
    if isinstance(byte_arg, models.BigUIntConstant):
        return models.BytesConstant(
            source_location=byte_arg.source_location,
            value=itob_eval(byte_arg.value),
            encoding=AVMBytesEncoding.base16,
        )
    if isinstance(byte_arg, models.Register):
        byte_arg_defn = get_definition(subroutine, byte_arg)
        if isinstance(byte_arg_defn, models.Assignment) and isinstance(
            byte_arg_defn.source, models.Intrinsic
        ):
            match byte_arg_defn.source:
                case models.Intrinsic(op=AVMOp.itob, args=[models.UInt64Constant(value=itob_arg)]):
                    return models.BytesConstant(
                        source_location=byte_arg_defn.source_location,
                        value=itob_arg.to_bytes(8, "big"),
                        encoding=AVMBytesEncoding.base16,
                    )
                case models.Intrinsic(
                    op=AVMOp.bzero, args=[models.UInt64Constant(value=bzero_arg)]
                ) if bzero_arg <= 64:
                    return models.BytesConstant(
                        source_location=byte_arg_defn.source_location,
                        value=b"\x00" * bzero_arg,
                        encoding=AVMBytesEncoding.base16,
                    )
    return None


def try_simplify_arithmetic_ops(
    subroutine: models.Subroutine, value: models.ValueProvider
) -> models.ValueProvider | None:
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
        case models.Intrinsic(op=AVMOp.btoi, args=[byte_arg], source_location=op_loc) if (
            byte_const := get_byte_constant(subroutine, byte_arg)
        ):
            return models.UInt64Constant(
                value=int.from_bytes(byte_const.value, byteorder="big", signed=False),
                source_location=op_loc,
            )
        case models.Intrinsic(
            args=[byte_arg], op=AVMOp.bitwise_not_bytes, source_location=op_loc
        ) if (byte_const := get_byte_constant(subroutine, byte_arg)) is not None:
            not_bites = models.BytesConstant(
                source_location=op_loc,
                value=bytes([x ^ 0xFF for x in byte_const.value]),
                encoding=byte_const.encoding,
            )
            logger.debug(f"Folded ~{byte_const.value!r} to {not_bites.value!r}")
            return not_bites
        case models.Intrinsic(op=AVMOp.len_, args=[byte_arg], source_location=op_loc) if (
            byte_const := get_byte_constant(subroutine, byte_arg)
        ) is not None:
            len_x = len(byte_const.value)
            logger.debug(
                f"Folded len({format_bytes(byte_const.value, byte_const.encoding)}) to {len_x}"
            )
            return models.UInt64Constant(source_location=op_loc, value=len_x)
        case models.Intrinsic(
            op=AVMOp.setbit,
            args=[byte_arg, models.UInt64Constant() as index, models.UInt64Constant() as value],
            source_location=op_loc,
        ) if (byte_const := get_byte_constant(subroutine, byte_arg)) is not None:
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
            args=[byte_arg, models.UInt64Constant() as index],
            source_location=op_loc,
        ) if (byte_const := get_byte_constant(subroutine, byte_arg)) is not None:
            binary_array = [
                x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
            ]
            the_bit = binary_array[index.value]
            return models.UInt64Constant(source_location=op_loc, value=int(the_bit))
        case models.Intrinsic(
            op=AVMOp.extract | AVMOp.extract3,
            immediates=[int(S), int(L)],
            args=[byte_arg],
            source_location=op_loc,
        ) | models.Intrinsic(
            op=AVMOp.extract | AVMOp.extract3,
            immediates=[],
            args=[byte_arg, models.UInt64Constant(value=S), models.UInt64Constant(value=L)],
            source_location=op_loc,
        ) if (
            byte_const := get_byte_constant(subroutine, byte_arg)
        ) is not None:
            if L == 0:
                extracted = byte_const.value[S:]
            else:
                extracted = byte_const.value[S : S + L]
            return models.BytesConstant(
                source_location=op_loc, encoding=byte_const.encoding, value=extracted
            )
        case models.Intrinsic(
            op=AVMOp.substring | AVMOp.substring3,
            immediates=[int(S), int(E)],
            args=[byte_arg],
            source_location=op_loc,
        ) | models.Intrinsic(
            op=AVMOp.substring | AVMOp.substring3,
            immediates=[],
            args=[byte_arg, models.UInt64Constant(value=S), models.UInt64Constant(value=E)],
            source_location=op_loc,
        ) if (
            byte_const := get_byte_constant(subroutine, byte_arg)
        ) is not None:
            if E < S:
                return None  # would fail at runtime, lets hope this is unreachable 😬
            extracted = byte_const.value[S:E]
            return models.BytesConstant(
                source_location=op_loc, encoding=byte_const.encoding, value=extracted
            )
        case models.Intrinsic(
            op=(
                AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64
            ) as extract_uint_op,
            args=[
                models.BytesConstant(value=bytes_value),
                models.UInt64Constant(value=offset),
            ],
            source_location=op_loc,
        ):
            bit_size = int(extract_uint_op.code.removeprefix("extract_uint"))
            byte_size = bit_size // 8
            extracted = bytes_value[offset : offset + byte_size]
            if len(extracted) != byte_size:
                return None  # would fail at runtime, lets hope this is unreachable 😬
            uint64_result = int.from_bytes(extracted, byteorder="big", signed=False)
            return models.UInt64Constant(
                value=uint64_result,
                source_location=op_loc,
            )
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
            args=[byte_arg_a, byte_arg_b],
            source_location=op_loc,
        ) if (
            (byte_const_a := get_byte_constant(subroutine, byte_arg_a)) is not None
            and (byte_const_b := get_byte_constant(subroutine, byte_arg_b)) is not None
        ):
            a = byte_const_a.value
            encoding_a = byte_const_a.encoding
            b = byte_const_b.value
            encoding_b = byte_const_b.encoding
            if encoding_a == encoding_b:
                target_encoding = encoding_a  # preserve encoding if both equal
            else:
                target_encoding = AVMBytesEncoding.base64  # go with most compact if they differ
            if bytes_op == AVMOp.concat:
                a_b = a + b
                logger.debug(
                    f"Folded concat({format_bytes(a, encoding_a)},"
                    f" {format_bytes(b, encoding_b)}) to {a_b!r}"
                )
                return models.BytesConstant(
                    source_location=op_loc, value=a_b, encoding=target_encoding
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
                    value=byte_wise(do_op, a, b), encoding=target_encoding, source_location=op_loc
                )
        case models.Intrinsic(
            op=AVMOp.concat, args=[models.Register() as byte_arg, byte_arg_b]
        ) if (
            (byte_const_b := get_byte_constant(subroutine, byte_arg_b)) is not None
            # left constant concats will automatically get folded, like "a" + "b" + var because
            # of the way they're linearized, but var + "a" + "b" won't be, so we special case it
            and (byte_arg_defn := get_definition(subroutine, byte_arg)) is not None
            and isinstance(byte_arg_defn, models.Assignment)
            and isinstance(byte_arg_defn.source, models.Intrinsic)
            and byte_arg_defn.source.op is AVMOp.concat
            and isinstance(prev_concat_lhs := byte_arg_defn.source.args[0], models.Register)
            and isinstance(
                maybe_byte_const_a := byte_arg_defn.source.args[1], models.BytesConstant
            )
        ):
            a = maybe_byte_const_a.value
            encoding_a = maybe_byte_const_a.encoding
            b = byte_const_b.value
            encoding_b = byte_const_b.encoding
            if encoding_a == encoding_b:
                target_encoding = encoding_a  # preserve encoding if both equal
            else:
                target_encoding = AVMBytesEncoding.base64  # go with most compact if they differ
            a_b = a + b
            logger.debug(
                f"Folded chained concat of {format_bytes(a, encoding_a)}"
                f"and {format_bytes(b, encoding_b)}) to {a_b!r}"
            )
            if maybe_byte_const_a.source_location is None and byte_const_b.source_location is None:
                loc = None
            else:
                loc = maybe_byte_const_a.source_location + byte_const_b.source_location  # type: ignore[operator]
            return attrs.evolve(
                value,
                args=[
                    prev_concat_lhs,
                    models.BytesConstant(value=a_b, encoding=target_encoding, source_location=loc),
                ],
            )
        case models.Intrinsic(
            args=[
                models.Register(atype=AVMType.uint64) as reg_a,
                models.Register(atype=AVMType.uint64) as reg_b,
            ],
            op=op,
        ):
            c: models.Value | int | None = None
            if reg_a == reg_b:
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
                        c = reg_a
            if c is not None:
                if isinstance(c, models.Value):
                    logger.debug(f"Folded {reg_a} {op} {reg_b} to {c}")
                    return c
                else:
                    logger.debug(f"Folded {reg_a} {op} {reg_b} to {c}")
                    return models.UInt64Constant(value=c, source_location=value.source_location)
        case models.Intrinsic(
            args=[
                models.Value(atype=AVMType.uint64) as a,
                models.Value(atype=AVMType.uint64) as b,
            ],
            op=op,
        ):
            c = None
            a_const = get_int_constant(a)
            b_const = get_int_constant(b)
            # 0 == b <-> !b
            if a_const == 0 and op == AVMOp.eq:
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
                    case AVMOp.div_floor if b_const != 0:
                        c = a_const // b_const
                    case AVMOp.mod if b_const != 0:
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
                        c = int(a_const and b_const)
                    case AVMOp.or_:
                        c = int(a_const or b_const)
                    case AVMOp.shl:
                        c = (a_const << b_const) % (2**64)
                    case AVMOp.shr:
                        c = a_const >> b_const
                    case AVMOp.exp:
                        if a_const == 0 and b_const == 0:
                            return None  # would fail at runtime, lets hope this is unreachable 😬
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
                    logger.debug(
                        f"Folded {a_const if a_const is not None else a}"
                        f" {op} {b_const if b_const is not None else b} to {c}"
                    )
                    return models.UInt64Constant(value=c, source_location=value.source_location)
        case models.Intrinsic(
            args=[
                models.Register(atype=AVMType.bytes) as reg_a,
                models.Register(atype=AVMType.bytes) as reg_b,
            ],
            op=op,
        ):
            c = None
            if reg_a == reg_b:
                match op:
                    case AVMOp.sub_bytes:
                        c = 0
                    case AVMOp.eq_bytes | AVMOp.eq:
                        c = 1
                    case AVMOp.neq_bytes | AVMOp.neq:
                        c = 0
                    case AVMOp.div_floor_bytes:
                        c = 1
            if c is not None:
                if isinstance(c, models.Value):
                    logger.debug(f"Folded {reg_a} {op} {reg_b} to {c}")
                    return c
                else:
                    logger.debug(f"Folded {reg_a} {op} {reg_b} to {c}")
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
            if a_const == 1 and op == AVMOp.mul_bytes:
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
                logger.debug(
                    f"Folded {a_const if a_const is not None else a}"
                    f" {op} {b_const if b_const is not None else b} to {c}"
                )
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
                    simplified = try_simplify_arithmetic_ops(subroutine, source)
                    if simplified is not None:
                        assignment.source = simplified
                        modified += 1

    return modified > 0
