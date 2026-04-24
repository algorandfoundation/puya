import typing
from collections.abc import Callable

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class StaticallyFailingOpValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        checker = _CHECKERS.get(intrinsic.op)
        if checker is not None:
            reason = checker(intrinsic)
            if reason is not None:
                logger.warning(
                    f"{reason}; will fail at runtime if reached",
                    location=intrinsic.source_location,
                )


def _check_add(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a + b > algo_constants.MAX_UINT64:
                return "uint64 addition of constants overflows"
    return None


def _check_mul(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a * b > algo_constants.MAX_UINT64:
                return "uint64 multiplication of constants overflows"
    return None


def _check_sub(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if b > a:
                return "uint64 subtraction of constants underflows"
    return None


def _check_div_floor(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [_, models.UInt64Constant(value=0)]:
            return "uint64 division by constant zero"
    return None


def _check_mod(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [_, models.UInt64Constant(value=0)]:
            return "uint64 modulo by constant zero"
    return None


def _check_exp(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a == 0 and b == 0:
                return "uint64 exp result is undefined"
            if a**b > algo_constants.MAX_UINT64:
                return "uint64 exp of constants overflows"
    return None


def _check_shift(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [_, models.UInt64Constant(value=b)]:
            if b >= 64:
                return "uint64 shift by constant amount >= 64"
    return None


def _check_btoi(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.BytesConstant(value=a_bytes)]:
            if len(a_bytes) > 8:
                return "btoi of constant bytes exceeds 8 bytes"
    return None


def _check_bzero(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a)]:
            if a > algo_constants.MAX_BYTES_LENGTH:
                return "bzero of constant length exceeds AVM stack byte limit"
    return None


def _check_extract(intrinsic: models.Intrinsic) -> str | None:
    # extract with immediates: S, L — L==0 extracts to end (valid iff S <= len)
    match intrinsic.args:
        case [arg]:
            match intrinsic.immediates:
                case [int(start), int(length)]:
                    max_len = _bytes_length_lower_bound(arg)
                    if start > max_len:
                        return "start index for extract is out of bounds"
                    if length != 0 and start + length > max_len:
                        return "end index for extract is out of bounds"
    return None


def _check_extract3(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [
            arg,
            models.UInt64Constant(value=start),
            models.UInt64Constant(value=length),
        ]:
            if start + length > _bytes_length_lower_bound(arg):
                return "extract3 buffer overflow"
    return None


def _check_substring(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg]:
            match intrinsic.immediates:
                case [_, int(end)]:
                    # note: we don't check if end is before start, TEAL model does this,
                    #       to match algod behaviour
                    if end > _bytes_length_lower_bound(arg):
                        return "substring buffer overflow"
    return None


def _check_substring3(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [
            arg,
            models.UInt64Constant(value=start),
            models.UInt64Constant(value=end),
        ]:
            if end < start:
                return "substring3 has end preceding start"
            if end > _bytes_length_lower_bound(arg):
                return "substring3 buffer overflow"
        case [
            arg,
            _,
            models.UInt64Constant(value=end),
        ]:
            if end > _bytes_length_lower_bound(arg):
                return "substring3 buffer overflow"
    return None


def _check_replace2(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg, models.BytesConstant(value=b_bytes)]:
            match intrinsic.immediates:
                case [int(start)] if start + len(b_bytes) > _bytes_length_lower_bound(arg):
                    return "replace2 buffer overflow"
    return None


def _check_replace3(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [
            arg,
            models.UInt64Constant(value=start),
            models.BytesConstant(value=b_bytes),
        ]:
            if start + len(b_bytes) > _bytes_length_lower_bound(arg):
                return "replace3 buffer overflow"
    return None


def _check_extract_uint(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=offset),
        ]:
            byte_size = {
                AVMOp.extract_uint16: 2,
                AVMOp.extract_uint32: 4,
                AVMOp.extract_uint64: 8,
            }[intrinsic.op]
            if offset + byte_size > len(a_bytes):
                return f"bytes constant is too small for {intrinsic.op.code}"
    return None


def _check_getbit(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg, models.UInt64Constant(value=index)]:
            match arg.ir_type.avm_type:
                case AVMType.uint64:
                    if index >= 64:
                        return "index for getbit of uint64 is out of bounds"
                case AVMType.bytes | AVMType.any:
                    if index >= (8 * _bytes_length_lower_bound(arg)):
                        return "index for getbit of bytes is out of bounds"
    return None


def _check_setbit(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg, models.UInt64Constant(value=index), _]:
            match arg.ir_type.avm_type:
                case AVMType.uint64:
                    if index >= 64:
                        return "index for setbit of uint64 is out of bounds"
                case AVMType.bytes | AVMType.any:
                    if index >= (8 * _bytes_length_lower_bound(arg)):
                        return "index for setbit of bytes is out of bounds"
    return None


def _check_getbyte(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [bytes_arg, models.UInt64Constant(value=index)]:
            if index >= _bytes_length_lower_bound(bytes_arg):
                return "index for getbyte is out of bounds"
    return None


def _check_setbyte(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [bytes_arg, models.UInt64Constant(value=index), _]:
            if index >= _bytes_length_lower_bound(bytes_arg):
                return "index for setbyte is out of bounds"
    return None


def _check_concat(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.BytesConstant(value=a), models.BytesConstant(value=b)]:
            if len(a) + len(b) > algo_constants.MAX_BYTES_LENGTH:
                return "concat buffer overflow"
    return None


_CHECKERS: dict[AVMOp, Callable[[models.Intrinsic], str | None]] = {
    AVMOp.add: _check_add,
    AVMOp.mul: _check_mul,
    AVMOp.sub: _check_sub,
    AVMOp.div_floor: _check_div_floor,
    AVMOp.mod: _check_mod,
    AVMOp.exp: _check_exp,
    AVMOp.shl: _check_shift,
    AVMOp.shr: _check_shift,
    AVMOp.btoi: _check_btoi,
    AVMOp.bzero: _check_bzero,
    AVMOp.extract: _check_extract,
    AVMOp.extract3: _check_extract3,
    AVMOp.substring: _check_substring,
    AVMOp.substring3: _check_substring3,
    AVMOp.replace2: _check_replace2,
    AVMOp.replace3: _check_replace3,
    AVMOp.extract_uint16: _check_extract_uint,
    AVMOp.extract_uint32: _check_extract_uint,
    AVMOp.extract_uint64: _check_extract_uint,
    AVMOp.getbit: _check_getbit,
    AVMOp.setbit: _check_setbit,
    AVMOp.getbyte: _check_getbyte,
    AVMOp.setbyte: _check_setbyte,
    AVMOp.concat: _check_concat,
}


def _bytes_length_lower_bound(arg: models.Value) -> int:
    match arg:
        case models.BytesConstant(value=value):
            return len(value)
        case _:
            return algo_constants.MAX_BYTES_LENGTH
