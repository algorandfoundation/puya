import typing

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
        case AVMOp.substring, [models.BytesConstant(value=a_bytes)]:
            match intrinsic.immediates:
                case [int(start), int(end)]:
                    if end < start:
                        return f"substring end {end} precedes start {start}"
                    if end > len(a_bytes):
                        return f"substring end {end} exceeds input length {len(a_bytes)}"
        case (
            AVMOp.substring3,
            [
                models.BytesConstant(value=a_bytes),
                models.UInt64Constant(value=start),
                models.UInt64Constant(value=end),
            ],
        ):
            if end < start:
                return f"substring end {end} precedes start {start}"
            if end > len(a_bytes):
                return f"substring end {end} exceeds input length {len(a_bytes)}"
        case (
            AVMOp.replace2,
            [models.BytesConstant(value=a_bytes), models.BytesConstant(value=b_bytes)],
        ):
            match intrinsic.immediates:
                case [int(start)] if start + len(b_bytes) > len(a_bytes):
                    return (
                        f"replace at offset {start} of {len(b_bytes)} bytes"
                        f" exceeds input length {len(a_bytes)}"
                    )
        case (
            AVMOp.replace3,
            [
                models.BytesConstant(value=a_bytes),
                models.UInt64Constant(value=start),
                models.BytesConstant(value=b_bytes),
            ],
        ):
            if start + len(b_bytes) > len(a_bytes):
                return (
                    f"replace at offset {start} of {len(b_bytes)} bytes"
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
