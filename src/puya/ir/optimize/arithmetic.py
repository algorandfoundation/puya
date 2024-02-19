import operator
import typing
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
from puya.utils import biguint_bytes_eval

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def arithmetic_simplification(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Simplify arithmetic expressions e.g. a-a -> 0, a*0 -> 0, a*1 -> a"""
    modified = 0

    for block in subroutine.body:
        for op in block.ops:
            match op:
                case models.Assignment(source=models.Intrinsic() as source) as assignment:
                    if source.op in (AVMOp.loads, AVMOp.gloads) or (
                        source.op.code.startswith("box_")
                    ):
                        # can't simplify these
                        pass
                    # we deliberately don't simplify these unless they're part of something else,
                    # since they can drastically increase program size
                    elif source.op in (AVMOp.itob, AVMOp.bzero):
                        pass
                    else:
                        simplified = _try_simplify_arithmetic_ops(subroutine, source)
                        if simplified is not None:
                            logger.debug(f"Simplified {source} to {simplified}")
                            assignment.source = simplified
                            modified += 1

    return modified > 0


def _try_simplify_arithmetic_ops(
    subroutine: models.Subroutine, intrinsic: models.Intrinsic
) -> models.ValueProvider | None:
    op_loc = intrinsic.source_location
    if intrinsic.op is AVMOp.getbit:
        match intrinsic.args:
            case [
                byte_arg,
                models.UInt64Constant(value=index),
            ] if (byte_const := _get_byte_constant(subroutine, byte_arg)) is not None:
                binary_array = [
                    x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
                ]
                the_bit = binary_array[index]
                return models.UInt64Constant(source_location=op_loc, value=int(the_bit))
    elif intrinsic.op is AVMOp.setbit:
        match intrinsic.args:
            case [
                byte_arg,
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ] if (byte_const := _get_byte_constant(subroutine, byte_arg)) is not None:
                binary_array = [
                    x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
                ]
                binary_array[index] = "1" if value else "0"
                binary_string = "".join(binary_array)
                adjusted_const_value = int(binary_string, 2).to_bytes(
                    len(byte_const.value), byteorder="big"
                )
                return models.BytesConstant(
                    source_location=op_loc,
                    encoding=byte_const.encoding,
                    value=adjusted_const_value,
                )
    elif intrinsic.op.code.startswith("extract_uint"):
        match intrinsic.args:
            case [
                models.BytesConstant(value=bytes_value),
                models.UInt64Constant(value=offset),
            ]:
                bit_size = int(intrinsic.op.code.removeprefix("extract_uint"))
                byte_size = bit_size // 8
                extracted = bytes_value[offset : offset + byte_size]
                if len(extracted) != byte_size:
                    return None  # would fail at runtime, lets hope this is unreachable 😬
                uint64_result = int.from_bytes(extracted, byteorder="big", signed=False)
                return models.UInt64Constant(
                    value=uint64_result,
                    source_location=op_loc,
                )
    elif intrinsic.op is AVMOp.concat:
        left_arg, right_arg = intrinsic.args
        left_const = _get_byte_constant(subroutine, left_arg)
        right_const = _get_byte_constant(subroutine, right_arg)
        if left_const is not None:
            if left_const.value == b"":
                return right_arg
            if right_const is not None:
                # two constants, just fold
                target_encoding = _choose_encoding(left_const.encoding, right_const.encoding)
                result_value = left_const.value + right_const.value
                result = models.BytesConstant(
                    value=result_value,
                    encoding=target_encoding,
                    source_location=op_loc,
                )
                return result
        elif right_const is not None:
            if right_const.value == b"":
                return left_arg
    elif intrinsic.op.code.startswith("extract"):
        match intrinsic:
            case (
                models.Intrinsic(
                    immediates=[int(S), int(L)],
                    args=[byte_arg],
                )
                | models.Intrinsic(
                    immediates=[],
                    args=[
                        byte_arg,
                        models.UInt64Constant(value=S),
                        models.UInt64Constant(value=L),
                    ],
                )
            ) if (byte_const := _get_byte_constant(subroutine, byte_arg)) is not None:
                if L == 0:
                    extracted = byte_const.value[S:]
                else:
                    extracted = byte_const.value[S : S + L]
                return models.BytesConstant(
                    source_location=op_loc, encoding=byte_const.encoding, value=extracted
                )
    elif intrinsic.op.code.startswith("substring"):
        match intrinsic:
            case (
                models.Intrinsic(
                    immediates=[int(S), int(E)],
                    args=[byte_arg],
                )
                | models.Intrinsic(
                    immediates=[],
                    args=[
                        byte_arg,
                        models.UInt64Constant(value=S),
                        models.UInt64Constant(value=E),
                    ],
                )
            ) if (byte_const := _get_byte_constant(subroutine, byte_arg)) is not None:
                if E < S:
                    return None  # would fail at runtime, lets hope this is unreachable 😬
                extracted = byte_const.value[S:E]
                return models.BytesConstant(
                    source_location=op_loc, encoding=byte_const.encoding, value=extracted
                )
    elif not intrinsic.immediates:
        match intrinsic.args:
            case [models.Value(atype=AVMType.uint64) as x]:
                return _try_simplify_uint64_unary_op(intrinsic, x)
            case [
                models.Value(atype=AVMType.uint64) as a,
                models.Value(atype=AVMType.uint64) as b,
            ]:
                return _try_simplify_uint64_binary_op(intrinsic, a, b)
            case [models.Value(atype=AVMType.bytes) as x]:
                return _try_simplify_bytes_unary_op(subroutine, intrinsic, x)
            case [
                models.Value(atype=AVMType.bytes) as a,
                models.Value(atype=AVMType.bytes) as b,
            ]:
                return _try_simplify_bytes_binary_op(subroutine, intrinsic, a, b)

    return None


def _get_int_constant(value: models.Value) -> int | None:
    if isinstance(value, models.UInt64Constant):
        return value.value
    return None


def _get_biguint_constant(
    subroutine: models.Subroutine, value: models.Value
) -> tuple[int, bytes, AVMBytesEncoding] | tuple[None, None, None]:
    if isinstance(value, models.BigUIntConstant):
        return value.value, biguint_bytes_eval(value.value), AVMBytesEncoding.base16
    byte_const = _get_byte_constant(subroutine, value)
    if byte_const is not None and len(byte_const.value) <= 64:
        return (
            int.from_bytes(byte_const.value, byteorder="big", signed=False),
            byte_const.value,
            byte_const.encoding,
        )
    return None, None, None


def _byte_wise(op: Callable[[int, int], int], lhs: bytes, rhs: bytes) -> bytes:
    return bytes([op(a, b) for a, b in zip_longest(lhs[::-1], rhs[::-1], fillvalue=0)][::-1])


def _choose_encoding(a: AVMBytesEncoding, b: AVMBytesEncoding) -> AVMBytesEncoding:
    if a == b:
        # preserve encoding if both equal
        return a
    else:
        # go with most compact if they differ
        return AVMBytesEncoding.base64


def _get_byte_constant(
    subroutine: models.Subroutine, byte_arg: models.Value
) -> models.BytesConstant | None:
    if isinstance(byte_arg, models.BytesConstant):
        return byte_arg
    if isinstance(byte_arg, models.BigUIntConstant):
        return models.BytesConstant(
            source_location=byte_arg.source_location,
            value=biguint_bytes_eval(byte_arg.value),
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
                        value=itob_arg.to_bytes(8, byteorder="big", signed=False),
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


def _try_simplify_uint64_unary_op(
    intrinsic: models.Intrinsic, arg: models.Value
) -> models.ValueProvider | None:
    op_loc = intrinsic.source_location
    x = _get_int_constant(arg)
    if x is not None:
        if intrinsic.op is AVMOp.not_:
            not_x = 0 if x else 1
            return models.UInt64Constant(value=not_x, source_location=op_loc)
        elif intrinsic.op is AVMOp.bitwise_not:
            inverted = x ^ 0xFFFFFFFFFFFFFFFF
            return models.UInt64Constant(value=inverted, source_location=op_loc)
        else:
            logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {x}")
    return None


def _try_simplify_bytes_unary_op(
    subroutine: models.Subroutine, intrinsic: models.Intrinsic, arg: models.Value
) -> models.ValueProvider | None:
    op_loc = intrinsic.source_location
    byte_const = _get_byte_constant(subroutine, arg)
    if byte_const is not None:
        if intrinsic.op is AVMOp.bitwise_not_bytes:
            inverted = bytes([x ^ 0xFF for x in byte_const.value])
            return models.BytesConstant(
                value=inverted, encoding=byte_const.encoding, source_location=op_loc
            )
        elif intrinsic.op is AVMOp.btoi:
            converted = int.from_bytes(byte_const.value, byteorder="big", signed=False)
            return models.UInt64Constant(value=converted, source_location=op_loc)
        elif intrinsic.op is AVMOp.len_:
            length = len(byte_const.value)
            return models.UInt64Constant(value=length, source_location=op_loc)
        else:
            logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {byte_const}")
    return None


def _try_simplify_uint64_binary_op(
    intrinsic: models.Intrinsic, a: models.Value, b: models.Value
) -> models.ValueProvider | None:
    op = intrinsic.op
    c: models.Value | int | None = None

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
    if c is None:
        a_const = _get_int_constant(a)
        b_const = _get_int_constant(b)
        # 0 == b <-> !b
        if a_const == 0 and op == AVMOp.eq:
            return attrs.evolve(intrinsic, op=AVMOp.not_, args=[b])
        # a == 0 <-> !a
        elif b_const == 0 and op == AVMOp.eq:
            return attrs.evolve(intrinsic, op=AVMOp.not_, args=[a])
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
                case _:
                    logger.debug(
                        f"Don't know how to simplify {a_const} {intrinsic.op.code} {b_const}"
                    )
    if not isinstance(c, int):
        return c
    if c < 0:
        # Value cannot be folded as it would result in a negative uint64
        return None
    return models.UInt64Constant(value=c, source_location=intrinsic.source_location)


def _try_simplify_bytes_binary_op(
    subroutine: models.Subroutine, intrinsic: models.Intrinsic, a: models.Value, b: models.Value
) -> models.ValueProvider | None:
    op = intrinsic.op
    op_loc = intrinsic.source_location
    c: models.Value | int | None = None

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
    if c is None:
        a_const, a_const_bytes, a_encoding = _get_biguint_constant(subroutine, a)
        b_const, b_const_bytes, b_encoding = _get_biguint_constant(subroutine, b)
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
            if typing.TYPE_CHECKING:
                assert a_const_bytes is not None
                assert b_const_bytes is not None
                assert a_encoding is not None
                assert b_encoding is not None
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
                case AVMOp.eq_bytes:
                    c = 1 if a_const == b_const else 0
                case AVMOp.neq_bytes:
                    c = 1 if a_const != b_const else 0
                case AVMOp.eq:
                    c = 1 if a_const_bytes == b_const_bytes else 0
                case AVMOp.neq:
                    c = 1 if a_const_bytes != b_const_bytes else 0
                case AVMOp.bitwise_or_bytes:
                    return models.BytesConstant(
                        value=_byte_wise(operator.or_, a_const_bytes, b_const_bytes),
                        encoding=_choose_encoding(a_encoding, b_encoding),
                        source_location=op_loc,
                    )
                case AVMOp.bitwise_and_bytes:
                    return models.BytesConstant(
                        value=_byte_wise(operator.and_, a_const_bytes, b_const_bytes),
                        encoding=_choose_encoding(a_encoding, b_encoding),
                        source_location=op_loc,
                    )
                case AVMOp.bitwise_xor_bytes:
                    return models.BytesConstant(
                        value=_byte_wise(operator.xor, a_const_bytes, b_const_bytes),
                        encoding=_choose_encoding(a_encoding, b_encoding),
                        source_location=op_loc,
                    )
                case _:
                    logger.debug(
                        f"Don't know how to simplify {a_const} {intrinsic.op.code} {b_const}"
                    )
    if not isinstance(c, int):
        return c
    if c < 0:
        # don't fold to a negative
        return None
    # could look at StackType of op_signature.returns, but some are StackType.any
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
        return models.UInt64Constant(value=c, source_location=intrinsic.source_location)
    else:
        return models.BigUIntConstant(value=c, source_location=intrinsic.source_location)
