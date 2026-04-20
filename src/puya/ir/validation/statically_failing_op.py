import typing
from collections.abc import Sequence

from puya import algo_constants, log
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import PrimitiveIRType
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class StaticallyFailingOpValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        reason = _check(intrinsic)
        if reason is not None:
            logger.warning(
                f"{intrinsic.op.code}: {reason}; will fail at runtime if reached",
                location=intrinsic.source_location,
            )


def _check(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.op, intrinsic.args:
        case AVMOp.add, [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a + b > algo_constants.MAX_UINT64:
                return f"{a} + {b} overflows uint64"
        case AVMOp.mul, [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a * b > algo_constants.MAX_UINT64:
                return f"{a} * {b} overflows uint64"
        case AVMOp.sub, [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if b > a:
                return f"{a} - {b} underflows uint64"
        case ((AVMOp.div_floor | AVMOp.mod), [_, models.UInt64Constant(value=0)]):
            return "division by zero"
        case AVMOp.exp, [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a == 0 and b == 0:
                return "0 ** 0 is undefined"
            if a**b > algo_constants.MAX_UINT64:
                return f"{a} ** {b} overflows uint64"
        case ((AVMOp.shl | AVMOp.shr), [_, models.UInt64Constant(value=b)]):
            if b >= 64:
                return f"shift amount {b} exceeds uint64 bit width"
        case AVMOp.btoi, [models.BytesConstant(value=a_bytes)]:
            if len(a_bytes) > 8:
                return f"btoi input length {len(a_bytes)} exceeds 8 bytes"
        case AVMOp.bzero, [models.UInt64Constant(value=a)]:
            if a > algo_constants.MAX_BYTES_LENGTH:
                return (
                    f"bzero length {a} exceeds AVM stack byte limit"
                    f" ({algo_constants.MAX_BYTES_LENGTH})"
                )
        case AVMOp.extract, [models.BytesConstant(value=a_bytes)]:
            # extract with immediates: S, L — L==0 extracts to end (valid iff S <= len)
            match intrinsic.immediates:
                case [int(start), int(length)]:
                    if length == 0:
                        if start > len(a_bytes):
                            return f"extract start {start} exceeds input length {len(a_bytes)}"
                    elif start + length > len(a_bytes):
                        return (
                            f"extract range [{start}, {start + length})"
                            f" exceeds input length {len(a_bytes)}"
                        )
        case (
            AVMOp.extract3,
            [
                models.BytesConstant(value=a_bytes),
                models.UInt64Constant(value=start),
                models.UInt64Constant(value=length),
            ],
        ):
            if start + length > len(a_bytes):
                return (
                    f"extract range [{start}, {start + length})"
                    f" exceeds input length {len(a_bytes)}"
                )
        case (
            (AVMOp.substring | AVMOp.substring3),
            [models.BytesConstant(value=a_bytes), *rest],
        ):
            s, e = _substring_start_end(intrinsic, rest)
            if s is not None and e is not None:
                if e < s:
                    return f"substring end {e} precedes start {s}"
                if e > len(a_bytes):
                    return f"substring end {e} exceeds input length {len(a_bytes)}"
        case (
            (AVMOp.replace2 | AVMOp.replace3),
            [
                models.BytesConstant(value=a_bytes),
                *rest,
            ],
        ):
            s, b_bytes = _replace_start_and_bytes(intrinsic, rest)
            if s is not None and b_bytes is not None and s + len(b_bytes) > len(a_bytes):
                return (
                    f"replace at offset {s} of {len(b_bytes)} bytes"
                    f" exceeds input length {len(a_bytes)}"
                )
        case (
            (AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64),
            [models.BytesConstant(value=a_bytes), models.UInt64Constant(value=offset)],
        ):
            byte_size = {
                AVMOp.extract_uint16: 2,
                AVMOp.extract_uint32: 4,
                AVMOp.extract_uint64: 8,
            }[intrinsic.op]
            if offset + byte_size > len(a_bytes):
                return (
                    f"{intrinsic.op.code} at offset {offset} requires {byte_size} bytes"
                    f" but input length is {len(a_bytes)}"
                )
        case (
            AVMOp.getbit,
            [
                models.UInt64Constant(ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
            ],
        ):
            if index >= 64:
                return f"bit index {index} exceeds uint64 bit width"
        case AVMOp.getbit, [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=index),
        ]:
            if index >= 8 * len(a_bytes):
                return f"bit index {index} exceeds input bit length {8 * len(a_bytes)}"
        case (
            AVMOp.setbit,
            [
                models.UInt64Constant(ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
                _,
            ],
        ):
            if index >= 64:
                return f"bit index {index} exceeds uint64 bit width"
        case AVMOp.setbit, [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=index),
            _,
        ]:
            if index >= 8 * len(a_bytes):
                return f"bit index {index} exceeds input bit length {8 * len(a_bytes)}"
        case AVMOp.getbyte, [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=index),
        ]:
            if index >= len(a_bytes):
                return f"byte index {index} exceeds input length {len(a_bytes)}"
        case AVMOp.setbyte, [
            models.BytesConstant(value=a_bytes),
            models.UInt64Constant(value=index),
            _,
        ]:
            if index >= len(a_bytes):
                return f"byte index {index} exceeds input length {len(a_bytes)}"
    return None


def _replace_start_and_bytes(
    intrinsic: models.Intrinsic, stack_rest: Sequence[models.Value]
) -> tuple[int | None, bytes | None]:
    # replace2 with imm: 2 stack args (A, B), 1 int immediate (S)
    # replace3 with stack args: 3 stack args (A, S, B), no immediates
    match intrinsic.op, intrinsic.immediates, stack_rest:
        case AVMOp.replace2, [int(s)], [models.BytesConstant(value=b_bytes)]:
            return s, b_bytes
        case AVMOp.replace3, [], [
            models.UInt64Constant(value=s),
            models.BytesConstant(value=b_bytes),
        ]:
            return s, b_bytes
    return None, None


def _substring_start_end(
    intrinsic: models.Intrinsic, stack_rest: Sequence[models.Value]
) -> tuple[int | None, int | None]:
    # substring with immediates: 1 stack arg, 2 int immediates (S, E)
    # substring3 with stack args: 3 stack args (bytes, S, E)
    if not stack_rest:
        match intrinsic.immediates:
            case [int(s), int(e)]:
                return s, e
    elif len(stack_rest) == 2:
        match stack_rest:
            case [models.UInt64Constant(value=s), models.UInt64Constant(value=e)]:
                return s, e
    return None, None
