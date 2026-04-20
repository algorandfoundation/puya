import typing

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class StaticallyFailingOpValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        reason = _check(intrinsic)
        if reason is not None:
            logger.warning(
                f"{reason}; will fail at runtime if reached",
                location=intrinsic.source_location,
            )


def _check(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.op, intrinsic.args:
        case AVMOp.add, [
            models.UInt64Constant(value=a),
            models.UInt64Constant(value=b),
        ]:
            if a + b > algo_constants.MAX_UINT64:
                return "uint64 addition of constants overflows"
        case AVMOp.mul, [
            models.UInt64Constant(value=a),
            models.UInt64Constant(value=b),
        ]:
            if a * b > algo_constants.MAX_UINT64:
                return "uint64 multiplication of constants overflows"
        case AVMOp.sub, [
            models.UInt64Constant(value=a),
            models.UInt64Constant(value=b),
        ]:
            if b > a:
                return "uint64 subtraction of constants underflows"
        case AVMOp.div_floor, [
            _,
            models.UInt64Constant(value=0),
        ]:
            return "uint64 division by constant zero"
        case AVMOp.mod, [
            _,
            models.UInt64Constant(value=0),
        ]:
            return "uint64 modulo by constant zero"
        case AVMOp.exp, [
            models.UInt64Constant(value=a),
            models.UInt64Constant(value=b),
        ]:
            if a == 0 and b == 0:
                return "uint64 exp result is undefined"
            if a**b > algo_constants.MAX_UINT64:
                return "uint64 exp of constants overflows"
        case AVMOp.shl | AVMOp.shr, [
            _,
            models.UInt64Constant(value=b),
        ]:
            if b >= 64:
                return "uint64 shift by constant amount >= 64"
        case AVMOp.btoi, [
            models.BytesConstant(value=a_bytes),
        ]:
            if len(a_bytes) > 8:
                return "btoi of constant bytes exceeds 8 bytes"
        case AVMOp.bzero, [
            models.UInt64Constant(value=a),
        ]:
            if a > algo_constants.MAX_BYTES_LENGTH:
                return "bzero of constant length exceeds AVM stack byte limit"
        case AVMOp.extract, [arg]:
            # extract with immediates: S, L — L==0 extracts to end (valid iff S <= len)
            match intrinsic.immediates:
                case [int(start), int(length)]:
                    max_len = _bytes_length_lower_bound(arg)
                    if start > max_len:
                        return "extract of bytes is out of bounds"
                    if length != 0 and start + length > max_len:
                        return "extract of bytes is out of bounds"
        case AVMOp.extract3, [
            arg,
            models.UInt64Constant(value=start),
            models.UInt64Constant(value=length),
        ]:
            if start + length > _bytes_length_lower_bound(arg):
                return "extract3 of bytes is out of bounds"
        case AVMOp.substring, [arg]:
            match intrinsic.immediates:
                case [_, int(end)]:
                    # note: we don't check if end is before start, TEAL model does this,
                    #       to match algod behaviour
                    if end > _bytes_length_lower_bound(arg):
                        return "substring of bytes is out of bounds"
        case AVMOp.substring3, [
            arg,
            models.UInt64Constant(value=start),
            models.UInt64Constant(value=end),
        ]:
            if end < start:
                return "substring3 has end preceding start"
            if end > _bytes_length_lower_bound(arg):
                return "substring3 of bytes is out of bounds"
        case AVMOp.substring3, [
            arg,
            _,
            models.UInt64Constant(value=end),
        ]:
            if end > _bytes_length_lower_bound(arg):
                return "substring3 of bytes is out of bounds"
        case AVMOp.replace2, [arg, models.BytesConstant(value=b_bytes)]:
            match intrinsic.immediates:
                case [int(start)] if start + len(b_bytes) > _bytes_length_lower_bound(arg):
                    return "replace2 of bytes is out of bounds"
        case AVMOp.replace3, [
            arg,
            models.UInt64Constant(value=start),
            models.BytesConstant(value=b_bytes),
        ]:
            if start + len(b_bytes) > _bytes_length_lower_bound(arg):
                return "replace3 of bytes is out of bounds"
        case AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64, [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=offset),
        ]:
            byte_size = {
                AVMOp.extract_uint16: 2,
                AVMOp.extract_uint32: 4,
                AVMOp.extract_uint64: 8,
            }[intrinsic.op]
            if offset + byte_size > len(a_bytes):
                return f"{intrinsic.op.code} of constant bytes is out of bounds"
        case AVMOp.getbit, [
            arg,
            models.UInt64Constant(value=index),
        ]:
            match arg.ir_type.avm_type:
                case AVMType.uint64:
                    if index >= 64:
                        return "getbit of uint64 index out of bounds"
                case AVMType.bytes | AVMType.any:
                    if index >= (8 * _bytes_length_lower_bound(arg)):
                        return "getbit of bytes index out of bounds"
        case AVMOp.setbit, [
            arg,
            models.UInt64Constant(value=index),
            _,
        ]:
            match arg.ir_type.avm_type:
                case AVMType.uint64:
                    if index >= 64:
                        return "setbit of uint64 index out of bounds"
                case AVMType.bytes | AVMType.any:
                    if index >= (8 * _bytes_length_lower_bound(arg)):
                        return "setbit of bytes index out of bounds"
        case AVMOp.getbyte, [
            bytes_arg,
            models.UInt64Constant(value=index),
        ]:
            if index >= _bytes_length_lower_bound(bytes_arg):
                return "getbyte index out of bounds"
        case AVMOp.setbyte, [
            bytes_arg,
            models.UInt64Constant(value=index),
            _,
        ]:
            if index >= _bytes_length_lower_bound(bytes_arg):
                return "setbyte index out of bounds"
    return None


def _bytes_length_lower_bound(arg: models.Value) -> int:
    match arg:
        case models.BytesConstant(value=value):
            return len(value)
        case _:
            return algo_constants.MAX_BYTES_LENGTH
