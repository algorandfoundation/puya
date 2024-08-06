import base64
import enum
import math
import operator
import typing
from collections.abc import Callable, Iterable
from itertools import zip_longest

import attrs

from puya import algo_constants, log
from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Assignment, BasicBlock, Intrinsic, UInt64Constant
from puya.ir.optimize._utils import get_definition
from puya.ir.types_ import AVMBytesEncoding, IRType
from puya.ir.visitor_mutator import IRMutator
from puya.utils import biguint_bytes_eval

logger = log.get_logger(__name__)


def intrinsic_simplifier(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = IntrinsicSimplifier.apply(subroutine)
    return modified > 0


@attrs.define
class IntrinsicSimplifier(IRMutator):
    subroutine: models.Subroutine
    modified: int = 0
    current_block: BasicBlock | None = None

    @classmethod
    def apply(cls, to: models.Subroutine) -> int:
        replacer = cls(to)
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified

    def visit_block(self, block: BasicBlock) -> None:
        self.current_block = block
        super().visit_block(block)
        self.current_block = None

    def visit_assignment(self, ass: Assignment) -> Assignment | None:
        match ass.source:
            case models.Intrinsic() as source:
                simplified = _try_fold_intrinsic(self.subroutine, source)
                if simplified is None:
                    simplified = _try_convert_stack_args_to_immediates(source)
                if simplified is not None:
                    logger.debug(f"Simplified {source} to {simplified}")
                    ass.source = simplified
                    self.modified += 1
        return ass

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> Intrinsic | None:
        # if we get here, it means either the intrinsic doesn't have a return or it's ignored,
        # in either case, the result has to be either an Op or None (ie delete),
        # so we don't invoke _try_fold_intrinsic here
        match intrinsic:
            case Intrinsic(op=AVMOp.assert_, args=[cond]):
                if isinstance(cond, models.UInt64Constant):
                    value = cond.value
                    if value:
                        self.modified += 1
                        return None
                    else:
                        # an assert 0 could be simplified to an err, but
                        # this would make it a ControlOp, so the block would
                        # need to be restructured
                        pass
                else:
                    assert_cond_maybe_simplified = _try_simplify_bool_condition(
                        self.subroutine, cond
                    )
                    if assert_cond_maybe_simplified is not None:
                        self.modified += 1
                        return attrs.evolve(intrinsic, args=[assert_cond_maybe_simplified])
            case Intrinsic(
                op=AVMOp.itxn_field,
                immediates=["ApprovalProgramPages" | "ClearStateProgramPages"],
                args=[models.BytesConstant(value=b"")],
            ):
                return None
            # remove some app allocation itxn_fields if they are not needed and
            # can be safely removed
            case Intrinsic(
                op=AVMOp.itxn_field,
                immediates=[
                    "ExtraProgramPages"
                    | "GlobalNumUint"
                    | "GlobalNumByteSlice"
                    | "LocalNumUint"
                    | "LocalNumByteSlice"
                ],
                args=[arg],
            ) as op if (state := _get_itxn_field_txn_sequence(self.current_block, op)) and (
                # if one of these fields is set multiple times in a transaction,
                # then only the last value set needs to be kept
                state == _ITxnFieldPosition.not_last_in_txn
                # if it is the last time the field is set in a txn (and all prior sets have been
                # removed) then it can also be removed if it is being set to the default value
                or (
                    state == _ITxnFieldPosition.last_in_txn
                    and isinstance(arg, UInt64Constant)
                    and arg.value == 0
                )
            ):
                return None
            case _:
                simplified = _try_convert_stack_args_to_immediates(intrinsic)
                if simplified is not None:
                    self.modified += 1
                    return simplified
        return intrinsic

    def visit_conditional_branch(self, branch: models.ConditionalBranch) -> models.ControlOp:
        branch_cond_maybe_simplified = _try_simplify_bool_condition(
            self.subroutine, branch.condition
        )
        if branch_cond_maybe_simplified is not None:
            self.modified += 1
            return attrs.evolve(branch, condition=branch_cond_maybe_simplified)
        return branch


class _ITxnFieldPosition(enum.StrEnum):
    last_in_txn = enum.auto()
    not_last_in_txn = enum.auto()
    unknown = enum.auto()


def _get_itxn_field_txn_sequence(
    current_block: BasicBlock | None, set_field: Intrinsic
) -> _ITxnFieldPosition:
    if current_block is None or set_field.op != AVMOp.itxn_field:
        raise InternalError("expect current block and itxn_field op", set_field.source_location)
    for itxn_fields in _get_matching_itxn_fields(current_block, set_field):
        if set_field in itxn_fields:
            return (
                _ITxnFieldPosition.last_in_txn
                if set_field == itxn_fields[-1]
                else _ITxnFieldPosition.not_last_in_txn
            )
    return _ITxnFieldPosition.unknown


def _get_matching_itxn_fields(
    block: BasicBlock, set_field: Intrinsic
) -> Iterable[list[Intrinsic]]:
    to_match = (set_field.op, set_field.immediates)
    matching_fields: list[Intrinsic] | None = None
    for op in block.ops:
        if not isinstance(op, Intrinsic):
            continue
        # begin a txn
        if op.op == AVMOp.itxn_begin:
            matching_fields = []
        # end/begin a txn
        elif op.op == AVMOp.itxn_next:
            if matching_fields is not None:
                yield matching_fields
            matching_fields = []
        # end a txn
        elif op.op == AVMOp.itxn_submit:
            if matching_fields is not None:
                yield matching_fields
            matching_fields = None
        elif matching_fields is not None and to_match == (op.op, op.immediates):
            matching_fields.append(op)


def _try_simplify_bool_condition(
    subroutine: models.Subroutine, cond: models.Value
) -> models.Value | None:
    if isinstance(cond, models.Register):
        cond_defn = get_definition(subroutine, cond)
        match cond_defn:
            case models.Assignment(
                source=models.Intrinsic(
                    args=[
                        models.Value(atype=AVMType.uint64) as a,
                        models.Value(atype=AVMType.uint64) as b,
                    ]
                ) as cond_op
            ):
                cond_maybe_simplified = _try_simplify_uint64_binary_op(
                    cond_op, a, b, bool_context=True
                )
                if isinstance(cond_maybe_simplified, models.Value):
                    return cond_maybe_simplified
    return None


def _try_convert_stack_args_to_immediates(intrinsic: Intrinsic) -> Intrinsic | None:
    match intrinsic:
        case Intrinsic(
            op=AVMOp.gitxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[group_index, field],
        ):
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gitxna,
                args=[],
                immediates=[group_index, field, array_index],
            )
        case Intrinsic(
            op=AVMOp.itxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[field],
        ):
            return attrs.evolve(
                intrinsic,
                op=AVMOp.itxna,
                args=[],
                immediates=[field, array_index],
            )
        case Intrinsic(
            op=(AVMOp.loads | AVMOp.stores as op),
            args=[models.UInt64Constant(value=slot), *rest],
        ):
            return attrs.evolve(
                intrinsic,
                immediates=[slot],
                args=rest,
                op=AVMOp.load if op == AVMOp.loads else AVMOp.store,
            )
        case Intrinsic(
            op=(AVMOp.extract3 | AVMOp.extract),
            args=[
                models.Value(atype=AVMType.bytes),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=L),
            ],
        ) if S <= 255 and 1 <= L <= 255:
            # note the lower bound of 1 on length, extract with immediates vs extract3
            # have *very* different behaviour if the length is 0
            return attrs.evolve(
                intrinsic, immediates=[S, L], args=intrinsic.args[:1], op=AVMOp.extract
            )
        case Intrinsic(
            op=AVMOp.substring3,
            args=[
                models.Value(atype=AVMType.bytes),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=E),
            ],
        ) if S <= 255 and E <= 255:
            return attrs.evolve(
                intrinsic, immediates=[S, E], args=intrinsic.args[:1], op=AVMOp.substring
            )
        case Intrinsic(
            op=AVMOp.replace3,
            args=[a, models.UInt64Constant(value=S), b],
        ) if S <= 255:
            return attrs.evolve(intrinsic, immediates=[S], args=[a, b], op=AVMOp.replace2)
        case Intrinsic(
            op=AVMOp.args,
            args=[models.UInt64Constant(value=idx)],
        ) if idx <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.arg, immediates=[idx], args=[])
    return None


def _try_fold_intrinsic(
    subroutine: models.Subroutine, intrinsic: models.Intrinsic
) -> models.ValueProvider | None:
    if intrinsic.op in (AVMOp.loads, AVMOp.gloads) or (
        intrinsic.op.code.startswith(("box_", "app_global_", "app_local_"))
    ):
        # can't simplify these
        return None
    elif intrinsic.op in (AVMOp.itob, AVMOp.bzero):
        # we deliberately don't simplify these unless they're part of something else,
        # since they can drastically increase program size
        return None

    op_loc = intrinsic.source_location
    if intrinsic.op is AVMOp.select:
        false, true, selector = intrinsic.args
        selector_const = _get_int_constant(selector)
        if selector_const is not None:
            return true if selector_const else false
        maybe_simplified_select_cond = _try_simplify_bool_condition(subroutine, selector)
        if maybe_simplified_select_cond is not None:
            return attrs.evolve(intrinsic, args=[false, true, maybe_simplified_select_cond])
        if false == true:
            return true
        match _get_byte_constant(subroutine, false), _get_byte_constant(subroutine, true):
            case (None, _) | (_, None):
                pass
            case (
                models.BytesConstant(value=false_value),
                models.BytesConstant(value=true_value) as true_bytes_const,
            ) if false_value == true_value:
                return true_bytes_const
        match _get_int_constant(false), _get_int_constant(true):
            case (None, _) | (_, None):
                pass
            case 1, 0:
                return attrs.evolve(intrinsic, op=AVMOp.not_, args=[selector])
            case 0, int(true_int_value) if selector.ir_type == IRType.bool:
                if true_int_value == 1:
                    return selector
                return attrs.evolve(intrinsic, op=AVMOp.mul, args=[selector, true])
            case 0, 1:
                zero_const = UInt64Constant(value=0, source_location=intrinsic.source_location)
                return attrs.evolve(intrinsic, op=AVMOp.neq, args=[selector, zero_const])
    elif intrinsic.op is AVMOp.getbit:
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
                try:
                    binary_array[index] = "1" if value else "0"
                except IndexError:
                    return None  # would fail at runtime
                binary_string = "".join(binary_array)
                adjusted_const_value = int(binary_string, 2).to_bytes(
                    len(byte_const.value), byteorder="big"
                )
                return models.BytesConstant(
                    source_location=op_loc,
                    encoding=byte_const.encoding,
                    value=adjusted_const_value,
                )
            case [a, b, c]:
                bool_arg_maybe_simplified = _try_simplify_bool_condition(subroutine, c)
                if bool_arg_maybe_simplified is not None:
                    return attrs.evolve(intrinsic, args=[a, b, bool_arg_maybe_simplified])
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
            case models.Intrinsic(
                immediates=[int(S), int(L)],
                args=[byte_arg],
            ) | models.Intrinsic(
                immediates=[],
                args=[
                    byte_arg,
                    models.UInt64Constant(value=S),
                    models.UInt64Constant(value=L),
                ],
            ) if (
                byte_const := _get_byte_constant(subroutine, byte_arg)
            ) is not None:
                # note there is a difference of behaviour between extract with stack args
                # and with immediates - zero is to the end with immediates,
                # and zero length with stacks
                if intrinsic.immediates and L == 0:
                    extracted = byte_const.value[S:]
                else:
                    extracted = byte_const.value[S : S + L]
                return models.BytesConstant(
                    source_location=op_loc, encoding=byte_const.encoding, value=extracted
                )
    elif intrinsic.op.code.startswith("substring"):
        match intrinsic:
            case models.Intrinsic(
                immediates=[int(S), int(E)],
                args=[byte_arg],
            ) | models.Intrinsic(
                immediates=[],
                args=[
                    byte_arg,
                    models.UInt64Constant(value=S),
                    models.UInt64Constant(value=E),
                ],
            ) if (
                byte_const := _get_byte_constant(subroutine, byte_arg)
            ) is not None:
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
    # exclude utf8 from known choices, we don't preserve that encoding choice unless
    # they're both utf8 strings, which is covered by the first check
    known_binary_choices = {a, b} - {AVMBytesEncoding.utf8, AVMBytesEncoding.unknown}
    if not known_binary_choices:
        return AVMBytesEncoding.unknown

    # pick the most compact encoding of the known binary encodings
    if AVMBytesEncoding.base64 in known_binary_choices:
        return AVMBytesEncoding.base64
    if AVMBytesEncoding.base32 in known_binary_choices:
        return AVMBytesEncoding.base32
    return AVMBytesEncoding.base16


def _decode_address(address: str) -> bytes:
    # Pad address so it's a valid b32 string
    padded_address = address + (6 * "=")
    address_bytes = base64.b32decode(padded_address)
    public_key_hash = address_bytes[: algo_constants.PUBLIC_KEY_HASH_LENGTH]
    return public_key_hash


def _get_byte_constant(
    subroutine: models.Subroutine, byte_arg: models.Value
) -> models.BytesConstant | None:
    if isinstance(byte_arg, models.BytesConstant):
        return byte_arg
    if isinstance(byte_arg, models.BigUIntConstant):
        return models.BytesConstant(
            value=biguint_bytes_eval(byte_arg.value),
            encoding=AVMBytesEncoding.base16,
            source_location=byte_arg.source_location,
        )
    if isinstance(byte_arg, models.AddressConstant):
        return models.BytesConstant(
            value=_decode_address(byte_arg.value),
            encoding=AVMBytesEncoding.base32,
            source_location=byte_arg.source_location,
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
                case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                    return models.BytesConstant(
                        value=_decode_address(algo_constants.ZERO_ADDRESS),
                        encoding=AVMBytesEncoding.base32,
                        source_location=byte_arg.source_location,
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
        elif intrinsic.op is AVMOp.sqrt:
            value = math.isqrt(x)
            return models.UInt64Constant(value=value, source_location=op_loc)
        else:
            logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {x}")
    return None


def _try_simplify_bytes_unary_op(
    subroutine: models.Subroutine, intrinsic: models.Intrinsic, arg: models.Value
) -> models.ValueProvider | None:
    op_loc = intrinsic.source_location
    if intrinsic.op is AVMOp.bsqrt:
        biguint_const, _, _ = _get_biguint_constant(subroutine, arg)
        if biguint_const is not None:
            value = math.isqrt(biguint_const)
            return models.BigUIntConstant(value=value, source_location=op_loc)
    else:
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
    intrinsic: models.Intrinsic, a: models.Value, b: models.Value, *, bool_context: bool = False
) -> models.ValueProvider | None:
    op = intrinsic.op
    c: models.Value | int | None = None

    if a == b:
        match op:
            case AVMOp.sub:
                c = 0
            case AVMOp.eq | AVMOp.lte | AVMOp.gte:
                c = 1
            case AVMOp.neq | AVMOp.lt | AVMOp.gt:
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
        # a >= 0 <-> 1
        elif b_const == 0 and op == AVMOp.gte:  # noqa: SIM114
            c = 1
        # 0 <= b <-> 1
        elif a_const == 0 and op == AVMOp.lte:
            c = 1
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
        # 0 != b <-> b
        #   OR
        # 0 < b <-> b
        elif (
            (bool_context or b.ir_type == IRType.bool)
            and a_const == 0
            and op in (AVMOp.neq, AVMOp.lt)
        ):
            c = b
        # a != 0 <-> a
        #   OR
        # a > 0 <-> a
        elif (
            (bool_context or a.ir_type == IRType.bool)
            and b_const == 0
            and op in (AVMOp.neq, AVMOp.gt)
        ):
            c = a
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
            case AVMOp.eq_bytes | AVMOp.eq | AVMOp.lte_bytes | AVMOp.gte_bytes:
                c = 1
            case AVMOp.neq_bytes | AVMOp.neq | AVMOp.lt_bytes | AVMOp.gt_bytes:
                c = 0
            case AVMOp.div_floor_bytes:
                c = 1
            case AVMOp.bitwise_xor_bytes:
                c = 0
            case AVMOp.bitwise_and_bytes | AVMOp.bitwise_or_bytes:
                c = a
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
                case AVMOp.mod_bytes if b_const != 0:
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
