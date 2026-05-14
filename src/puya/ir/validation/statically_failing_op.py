import operator
import typing
from collections.abc import Callable, Mapping, Sequence

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import (
    models,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


Checker = Callable[[models.Intrinsic], str | None]


class StaticallyFailingOpValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        for checker in (_check_signature_constrained_args, *_CHECKERS.get(intrinsic.op, ())):
            if problem := checker(intrinsic):
                logger.warning(
                    f"{problem}; will fail at runtime if reached",
                    location=intrinsic.source_location,
                )
                return


# region Checker factories
def _make_uint64_result_check(
    reducer: Callable[[int, int], int],
) -> Checker:
    def check(intrinsic: models.Intrinsic) -> str | None:
        match intrinsic.args:
            case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
                result = reducer(a, b)
                if result > algo_constants.MAX_UINT64:
                    return "uint64 constant overflow"
                if result < 0:
                    return "uint64 constant underflow"
        return None

    return check


def _make_uint64_const_arg_checker(
    idx: int, predicate: Callable[[int], bool], fail_message: str
) -> Checker:
    def check(intrinsic: models.Intrinsic) -> str | None:
        match intrinsic.args[idx]:
            case models.UInt64Constant(value=value):
                if not predicate(value):
                    return fail_message
        return None

    return check


def _make_bytes_const_arg_checker(
    idx: int, predicate: Callable[[bytes], bool], fail_message: str
) -> Checker:
    def check(intrinsic: models.Intrinsic) -> str | None:
        value = _get_bytes_constant_value(intrinsic.args[idx])
        if value is not None and not predicate(value):
            return fail_message
        return None

    return check


def _make_biguint_const_arg_checker(
    idx: int, predicate: Callable[[int], bool], fail_message: str
) -> Checker:
    def check(intrinsic: models.Intrinsic) -> str | None:
        maybe_const = _get_biguint_constant_value(intrinsic.args[idx])
        if maybe_const is not None and not predicate(maybe_const):
            return fail_message
        return None

    return check


def _make_extract_uint_check(
    op: typing.Literal[AVMOp.extract_uint16, AVMOp.extract_uint32, AVMOp.extract_uint64],
) -> Checker:
    match op:
        case AVMOp.extract_uint16:
            byte_size = 2
        case AVMOp.extract_uint32:
            byte_size = 4
        case AVMOp.extract_uint64:
            byte_size = 8
        case unexpected:
            typing.assert_never(unexpected)

    def check(intrinsic: models.Intrinsic) -> str | None:
        assert intrinsic.op is op
        match intrinsic.args:
            case [bytes_arg, models.UInt64Constant(value=offset)]:
                if offset + byte_size > _bytes_length_or_max(bytes_arg):
                    return f"{intrinsic.op.code} buffer over-read"
        return None

    return check


# endregion


# region Multi-op handlers
def _check_get_or_set_bit_index(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg, models.UInt64Constant(value=index), *_]:
            match arg.ir_type.avm_type:
                case AVMType.uint64:
                    if index >= 64:
                        return "bit index of uint64 is out of bounds"
                case AVMType.bytes | AVMType.any:
                    if index >= (8 * _bytes_length_or_max(arg)):
                        return "bit index of bytes is out of bounds"
    return None


def _check_get_or_set_byte_index(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [bytes_arg, models.UInt64Constant(value=index), *_]:
            if index >= _bytes_length_or_max(bytes_arg):
                return "byte index of bytes is out of bounds"
    return None


def _check_signature_constrained_args(intrinsic: models.Intrinsic) -> str | None:
    # Validates constant operands against constraints implied by the op's declared arg types.
    # biguint *results* exceeding 512 bits are valid on the AVM, but cannot be re-consumed
    # as a biguint operand, so we surface the failure at the consuming op instead.
    for arg, expected_type in zip(intrinsic.args, intrinsic.op_signature.args, strict=True):
        match expected_type:
            case types.PrimitiveIRType.state_key:
                bytes_value = _get_bytes_constant_value(arg)
                if (
                    bytes_value is not None
                    and len(bytes_value) > algo_constants.MAX_STATE_KEY_LENGTH
                ):
                    return "state key constant exceeds 64 bytes"
            case types.PrimitiveIRType.box_key:
                bytes_value = _get_bytes_constant_value(arg)
                if bytes_value is not None and not (
                    algo_constants.MIN_BOX_KEY_LENGTH
                    <= len(bytes_value)
                    <= algo_constants.MAX_BOX_KEY_LENGTH
                ):
                    return "box key constant has invalid length (must be 1-64 bytes)"
            case types.PrimitiveIRType.biguint:
                bytes_value = _get_bytes_constant_value(arg)
                biguint_value = _get_biguint_constant_value(arg)
                if (
                    bytes_value is not None and len(bytes_value) > algo_constants.MAX_BIGUINT_BYTES
                ) or (
                    biguint_value is not None
                    and biguint_value.bit_length() > algo_constants.MAX_BIGUINT_BITS
                ):
                    return "biguint constant operand exceeds 512 bits"
    return None


# endregion


# region Specific op handlers
def _check_exp_undefined(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [models.UInt64Constant(value=a), models.UInt64Constant(value=b)]:
            if a == 0 and b == 0:
                return "uint64 exp result is undefined"
    return None


def _check_extract(intrinsic: models.Intrinsic) -> str | None:
    # extract with immediates: S, L — L==0 extracts to end (valid iff S <= len)
    (arg,) = intrinsic.args
    start, length = intrinsic.immediates
    assert isinstance(start, int)
    assert isinstance(length, int)
    max_len = _bytes_length_or_max(arg)
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
            if start + length > _bytes_length_or_max(arg):
                return "extract3 buffer overflow"
    return None


def _check_substring(intrinsic: models.Intrinsic) -> str | None:
    # note: we don't check if end is before start, TEAL model does this, to match algod behaviour
    (arg,) = intrinsic.args
    _, end = intrinsic.immediates
    assert isinstance(end, int)
    if end > _bytes_length_or_max(arg):
        return "substring buffer overflow"
    return None


def _check_substring3(intrinsic: models.Intrinsic) -> str | None:
    arg, start_val, end_val = intrinsic.args
    max_arg_len = _bytes_length_or_max(arg)
    start = None
    if isinstance(start_val, models.UInt64Constant):
        start = start_val.value
        if start > max_arg_len:
            return "substring3 buffer over-read"
    end = None
    if isinstance(end_val, models.UInt64Constant):
        end = end_val.value
        if end > max_arg_len:
            return "substring3 buffer over-read"
    if start is not None and end is not None and end < start:
        return "substring3 has end preceding start"
    return None


def _check_replace2(intrinsic: models.Intrinsic) -> str | None:
    arg, replacement_arg = intrinsic.args
    replacement = _get_bytes_constant_value(replacement_arg)
    if replacement is None:
        return None
    (start,) = intrinsic.immediates
    assert isinstance(start, int)
    if start + len(replacement) > _bytes_length_or_max(arg):
        return "replace2 buffer overflow"
    return None


def _check_replace3(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args:
        case [arg, models.UInt64Constant(value=start), replacement_arg]:
            replacement = _get_bytes_constant_value(replacement_arg)
            if replacement is not None and start + len(replacement) > _bytes_length_or_max(arg):
                return "replace3 buffer overflow"
    return None


def _check_concat(intrinsic: models.Intrinsic) -> str | None:
    a = _get_bytes_constant_value(intrinsic.args[0])
    b = _get_bytes_constant_value(intrinsic.args[1])
    if a is not None and b is not None and len(a) + len(b) > algo_constants.MAX_BYTES_LENGTH:
        return "concat buffer overflow"
    return None


def _check_biguint_sub_underflow(intrinsic: models.Intrinsic) -> str | None:
    a, b = intrinsic.args
    a_const = _get_biguint_constant_value(a)
    b_const = _get_biguint_constant_value(b)
    if a_const is not None and b_const is not None and a_const - b_const < 0:
        return "biguint constant underflow"
    return None


# endregion


def _get_bytes_constant_value(value: models.Value) -> bytes | None:
    match value:
        case models.BytesConstant(value=byte_value):
            return byte_value
        case _:
            return None


def _get_biguint_constant_value(value: models.Value) -> int | None:
    match value:
        case models.BigUIntConstant(value=v):
            return v
        case models.BytesConstant(value=byte_value):
            return int.from_bytes(byte_value, byteorder="big", signed=False)
        case _:
            return None


def _bytes_length_or_max(arg: models.Value) -> int:
    bytes_value = _get_bytes_constant_value(arg)
    return len(bytes_value) if bytes_value is not None else algo_constants.MAX_BYTES_LENGTH


def _make_scratch_slot_check(idx: int) -> Checker:
    return _make_uint64_const_arg_checker(
        idx,
        lambda x: x <= algo_constants.MAX_SCRATCH_SLOT_NUMBER,
        "scratch slot id constant exceeds 255",
    )


def _make_uint8_stack_arg_check(idx: int, description: str) -> Checker:
    return _make_uint64_const_arg_checker(
        idx,
        lambda x: x <= 255,
        f"{description} constant exceeds uint8 range (255)",
    )


def _check_txn_group_index_arg(intrinsic: models.Intrinsic) -> str | None:
    match intrinsic.args[0]:
        case models.UInt64Constant(value=value):
            if value >= algo_constants.MAX_TRANSACTION_GROUP_SIZE:
                return "txn group index constant exceeds maximum group size"
    return None


def _check_txn_group_index_immediate(intrinsic: models.Intrinsic) -> str | None:
    t = intrinsic.immediates[0]
    assert isinstance(t, int)
    if t >= algo_constants.MAX_TRANSACTION_GROUP_SIZE:
        return "txn group index immediate exceeds maximum group size"
    return None


_CHECKERS: typing.Final[Mapping[AVMOp, Sequence[Checker]]] = {
    AVMOp.add: [
        _make_uint64_result_check(operator.add),
    ],
    AVMOp.mul: [
        _make_uint64_result_check(operator.mul),
    ],
    AVMOp.sub: [
        _make_uint64_result_check(operator.sub),
    ],
    AVMOp.div_floor: [
        _make_uint64_const_arg_checker(1, lambda x: x != 0, "uint64 division by constant zero"),
    ],
    AVMOp.mod: [
        _make_uint64_const_arg_checker(1, lambda x: x != 0, "uint64 modulo by constant zero"),
    ],
    AVMOp.exp: [
        _make_uint64_result_check(operator.pow),
        _check_exp_undefined,
    ],
    AVMOp.shl: [
        _make_uint64_const_arg_checker(
            1, lambda x: x < 64, "uint64 shift by invalid constant amount"
        ),
    ],
    AVMOp.shr: [
        _make_uint64_const_arg_checker(
            1, lambda x: x < 64, "uint64 shift by invalid constant amount"
        ),
    ],
    AVMOp.btoi: [
        _make_bytes_const_arg_checker(
            0, lambda x: len(x) <= 8, "btoi of constant bytes exceeds 8 bytes"
        ),
    ],
    AVMOp.bzero: [
        _make_uint64_const_arg_checker(
            0,
            lambda x: x <= algo_constants.MAX_BYTES_LENGTH,
            "bzero of constant length exceeds AVM stack byte limit",
        ),
    ],
    AVMOp.extract_uint16: [
        _make_extract_uint_check(AVMOp.extract_uint16),
    ],
    AVMOp.extract_uint32: [
        _make_extract_uint_check(AVMOp.extract_uint32),
    ],
    AVMOp.extract_uint64: [
        _make_extract_uint_check(AVMOp.extract_uint64),
    ],
    AVMOp.extract: [_check_extract],
    AVMOp.extract3: [_check_extract3],
    AVMOp.substring: [_check_substring],
    AVMOp.substring3: [_check_substring3],
    AVMOp.replace2: [_check_replace2],
    AVMOp.replace3: [_check_replace3],
    AVMOp.getbit: [_check_get_or_set_bit_index],
    AVMOp.setbit: [_check_get_or_set_bit_index],
    AVMOp.getbyte: [_check_get_or_set_byte_index],
    AVMOp.setbyte: [_check_get_or_set_byte_index],
    AVMOp.concat: [_check_concat],
    AVMOp.sub_bytes: [_check_biguint_sub_underflow],
    AVMOp.div_floor_bytes: [
        _make_biguint_const_arg_checker(1, lambda x: x != 0, "biguint division by constant zero"),
    ],
    AVMOp.mod_bytes: [
        _make_biguint_const_arg_checker(1, lambda x: x != 0, "biguint modulo by constant zero"),
    ],
    AVMOp.box_extract: [
        _make_uint64_const_arg_checker(
            2,
            lambda x: x <= algo_constants.MAX_BYTES_LENGTH,
            "box_extract length exceeds AVM stack byte limit",
        ),
    ],
    # group ops
    AVMOp.gaid: [_check_txn_group_index_immediate],
    AVMOp.gaids: [_check_txn_group_index_arg],
    AVMOp.gload: [_check_txn_group_index_immediate],
    AVMOp.gloads: [_check_txn_group_index_arg],
    AVMOp.gloadss: [_check_txn_group_index_arg, _make_scratch_slot_check(1)],
    AVMOp.gtxn: [_check_txn_group_index_immediate],
    AVMOp.gtxna: [_check_txn_group_index_immediate],
    AVMOp.gtxns: [_check_txn_group_index_arg],
    AVMOp.gtxnas: [
        _check_txn_group_index_immediate,
        _make_uint8_stack_arg_check(0, "txn array field index"),
    ],
    AVMOp.gtxnsa: [_check_txn_group_index_arg],
    AVMOp.gtxnsas: [
        _check_txn_group_index_arg,
        _make_uint8_stack_arg_check(1, "txn array field index"),
    ],
    AVMOp.gitxn: [_check_txn_group_index_immediate],
    AVMOp.gitxna: [_check_txn_group_index_immediate],
    AVMOp.gitxnas: [
        _check_txn_group_index_immediate,
        _make_uint8_stack_arg_check(0, "inner txn array field index"),
    ],
    # scratch slot id (immediate-form ops are constrained at parse time by uint8)
    AVMOp.loads: [_make_scratch_slot_check(0)],
    AVMOp.stores: [_make_scratch_slot_check(0)],
    # uint8 stack args (counterparts of uint8 immediate-form ops)
    AVMOp.txnas: [_make_uint8_stack_arg_check(0, "txn array field index")],
    AVMOp.itxnas: [_make_uint8_stack_arg_check(0, "inner txn array field index")],
}
