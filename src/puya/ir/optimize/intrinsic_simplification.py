import functools
import operator
import typing
from collections import deque
from collections.abc import Callable, Container, Mapping

import attrs

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import models
from puya.ir._utils import get_bytes_constant
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Intrinsic, UInt64Constant
from puya.ir.optimize._intrinsics import (
    COMPILE_TIME_CONSTANT_OPS,
    EXTRACT_UINTN_BYTE_SIZE,
    SIDE_EFFECT_FREE_AVM_OPS,
    BinarySimplification,
    choose_encoding,
    chop_encoding,
    fold_extract_uint_n,
    fold_getbit_bytes,
    fold_getbyte,
    fold_replace2,
    fold_setbit_bytes,
    fold_setbit_uint64,
    fold_setbyte,
    simplify_uint64_binary_op_one_const,
    valid_uint64,
)
from puya.ir.optimize._utils import SSAReadTracker
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import Address, biguint_bytes_eval, biguint_bytes_length, set_add

logger = log.get_logger(__name__)

_RegisterAssignments = Mapping[models.Value, models.Assignment]


def intrinsic_simplifier(context: IROptimizationContext, subroutine: models.Subroutine) -> bool:
    work_list = _AssignmentWorkQueue(COMPILE_TIME_CONSTANT_OPS)
    ssa_reads = SSAReadTracker()

    register_assignments = dict[models.Value, models.Assignment]()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)
            if isinstance(op, models.Assignment):
                work_list.enqueue(op)
                if len(op.targets) == 1:
                    (target,) = op.targets
                    register_assignments[target] = op

    modified = 0
    while work_list:
        ass, source = work_list.dequeue()
        simplified = _try_fold_intrinsic(context, ssa_reads, register_assignments, source)
        if simplified is None:
            simplified = _try_simplify_repeated_binary_op(
                register_assignments, ass, source, ssa_reads
            )
        if simplified is not None:
            logger.debug(f"Simplified {source} to {simplified}")
            with ssa_reads.update(ass):
                ass.source = simplified
            modified += 1
            # if it became a Value, propagate to any assignment-readers and add to work list
            if isinstance(simplified, models.Value):
                (target,) = ass.targets
                replacer = _RegisterValueReplacer(register=target, replacement=simplified)
                for target_read in ssa_reads.get(target, copy=True):
                    if isinstance(target_read, models.Assignment):
                        work_list.enqueue(target_read)
                        # special case for indirection of otherwise non-inlined constants
                        match target_read:
                            case models.Assignment(
                                targets=[target_read_target],
                                source=models.Intrinsic(op=(AVMOp.bzero | AVMOp.itob)),
                            ) if not context.expand_all_bytes:
                                for indirect_target_read in ssa_reads.get(target_read_target):
                                    if isinstance(indirect_target_read, models.Assignment):
                                        work_list.enqueue(indirect_target_read)
                    with ssa_reads.update(target_read):
                        target_read.accept(replacer)
                modified += replacer.modified
            else:
                typing.assert_type(simplified, models.Intrinsic)
                # source is still an intrinsic, add it back to the work list
                work_list.enqueue(ass)
                # add any assignment-readers to the work list
                for target in ass.targets:
                    for target_read in ssa_reads.get(target):
                        if isinstance(target_read, models.Assignment):
                            work_list.enqueue(target_read)

    for block in subroutine.body:
        for op in block.ops:
            match op:
                case (
                    models.Assignment(
                        source=models.Intrinsic(op=AVMOp.box_get) as intrinsic
                    ) as ass
                ):
                    maybe_value, exists = ass.targets
                    if ssa_reads.count(maybe_value) == 0:
                        logger.debug(
                            f"replacing box_get with box_len"
                            f" because {maybe_value.local_id} is unused"
                        )
                        modified += 1
                        # we've checked this isn't used, so it's safe to just change it's type
                        ass.targets[0] = attrs.evolve(maybe_value, ir_type=PrimitiveIRType.uint64)
                        ass.source = attrs.evolve(
                            intrinsic,
                            op=AVMOp.box_len,
                            types=(PrimitiveIRType.uint64, PrimitiveIRType.bool),
                        )
    register_intrinsics = {
        target: ass.source
        for target, ass in register_assignments.items()
        if isinstance(ass.source, models.Intrinsic)
    }
    modified += _simplify_conditional_branches(subroutine, register_intrinsics)
    modified += _simplify_non_returning_intrinsics(subroutine, register_intrinsics)
    return modified > 0


class _AssignmentWorkQueue:
    def __init__(self, constant_evaluable: Container[str]) -> None:
        self._constant_evaluable = constant_evaluable
        self._dq = deque[tuple[models.Assignment, models.Intrinsic]]()
        self._set = set[models.Assignment]()

    def enqueue(self, op: models.Assignment) -> bool:
        if (
            # TODO: currently, only single-value returning intrinsics are supported,
            #       but ops such as addw could be constant folded as well
            len(op.targets) == 1
            and isinstance(op.source, models.Intrinsic)
            and op.source.op.code in self._constant_evaluable
            and set_add(self._set, op)
        ):
            self._dq.append((op, op.source))
            return True
        return False

    def dequeue(self) -> tuple[models.Assignment, models.Intrinsic]:
        op, source = self._dq.popleft()
        assert source is op.source
        self._set.remove(op)
        return op, source

    def __bool__(self) -> int:
        return bool(self._dq)


@attrs.define(kw_only=True)
class _RegisterValueReplacer(IRMutator):
    register: models.Register
    replacement: models.Value
    modified: int = 0

    @typing.override
    def visit_register_define(self, _reg: models.Register) -> None:
        pass

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # don't visit phi nodes / args, needs to stay as Register
        pass

    @typing.override
    def visit_register(self, reg: models.Register) -> models.Value | None:
        if reg != self.register:
            return None
        self.modified += 1
        return self.replacement


def _simplify_conditional_branches(
    subroutine: models.Subroutine, register_intrinsics: Mapping[models.Value, models.Intrinsic]
) -> int:
    modified = 0
    branch_registers = dict[
        models.Register, list[tuple[models.ConditionalBranch, models.BasicBlock]]
    ]()
    for block in subroutine.body:
        match block.terminator:
            case (
                models.ConditionalBranch(condition=models.Register() as cond) as branch
            ) if cond in register_intrinsics:
                branch_registers.setdefault(cond, []).append((branch, block))
    for target, usages in branch_registers.items():
        intrinsic = register_intrinsics[target]
        cond_maybe_simplified = _try_simplify_bool_intrinsic(intrinsic)
        if cond_maybe_simplified is not None:
            for branch, used_block in usages:
                used_block.terminator = attrs.evolve(branch, condition=cond_maybe_simplified)
                modified += 1
    return modified


def _simplify_non_returning_intrinsics(
    subroutine: models.Subroutine, register_intrinsics: Mapping[models.Value, models.Intrinsic]
) -> int:
    modified = 0
    for block in subroutine.body:
        ops = list[models.Op]()
        result: models.Op | None
        for op in block.ops:
            if isinstance(op, models.Intrinsic):
                result = _visit_intrinsic_op(op)
                if result is not op:
                    modified += 1
                if result is not None:
                    ops.append(result)
            elif isinstance(op, models.Assert):
                result = _simplify_assert(op, register_intrinsics)
                if result is not op:
                    modified += 1
                if result is not None:
                    ops.append(result)
            else:
                ops.append(op)
        block.ops[:] = ops
    return modified


def _simplify_assert(
    assert_: models.Assert, register_intrinsics: Mapping[models.Value, models.Intrinsic]
) -> models.Assert | None:
    result: models.Assert | None = assert_
    cond = assert_.condition
    if isinstance(cond, models.UInt64Constant):
        value = cond.value
        if value:
            result = None
        else:
            # an assert 0 could be simplified to an err, but
            # this would make it a ControlOp, so the block would
            # need to be restructured
            pass
    elif cond_op := register_intrinsics.get(cond):
        assert_cond_maybe_simplified = _try_simplify_bool_intrinsic(cond_op)
        if assert_cond_maybe_simplified is not None:
            result = attrs.evolve(assert_, condition=assert_cond_maybe_simplified)
    return result


def _visit_intrinsic_op(intrinsic: Intrinsic) -> Intrinsic | None:
    # if we get here, it means either the intrinsic doesn't have a return or it's ignored,
    # in either case, the result has to be either an Op or None (ie delete),
    # so we don't invoke _try_fold_intrinsic here
    if intrinsic.op == AVMOp.itxn_field:
        (field_im,) = intrinsic.immediates
        if field_im in ("ApprovalProgramPages", "ClearStateProgramPages"):
            (page_value,) = intrinsic.args
            if isinstance(page_value, models.BytesConstant) and page_value.value == b"":
                return None
        return intrinsic
    elif intrinsic.op.code in SIDE_EFFECT_FREE_AVM_OPS:
        logger.debug(f"Removing unused pure op {intrinsic}")
        return None
    else:
        return intrinsic


def _try_simplify_bool_condition(
    register_assignments: _RegisterAssignments, cond: models.Value
) -> models.Value | None:
    if cond_defn := register_assignments.get(cond):
        return _try_simplify_bool_intrinsic(cond_defn.source)
    return None


def _try_simplify_bool_intrinsic(cond_op: models.ValueProvider) -> models.Value | None:
    match cond_op:
        case (
            models.Intrinsic(
                args=[
                    models.Value(atype=AVMType.uint64) as a,
                    models.Value(atype=AVMType.uint64) as b,
                ]
            ) as intrinsic
        ):
            cond_maybe_simplified = _try_simplify_uint64_binary_op(
                {}, intrinsic, a, b, bool_context=True
            )
            if isinstance(cond_maybe_simplified, models.Value):
                return cond_maybe_simplified
    return None


def _try_fold_intrinsic(
    context: IROptimizationContext,
    ssa_reads: SSAReadTracker,
    register_assignments: _RegisterAssignments,
    intrinsic: models.Intrinsic,
) -> models.Value | models.Intrinsic | None:
    op_loc = intrinsic.source_location
    if intrinsic.op is AVMOp.select:
        false, true, selector = intrinsic.args
        selector_const = _get_int_constant(selector)
        if selector_const is not None:
            return true if selector_const else false
        maybe_simplified_select_cond = _try_simplify_bool_condition(register_assignments, selector)
        if maybe_simplified_select_cond is not None:
            return attrs.evolve(intrinsic, args=[false, true, maybe_simplified_select_cond])
        if false == true:
            return true
        match (
            _get_byte_constant(register_assignments, false),
            _get_byte_constant(register_assignments, true),
        ):
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
            case 0, int(true_int_value) if selector.ir_type == PrimitiveIRType.bool:
                if true_int_value == 1:
                    return selector
                return attrs.evolve(intrinsic, op=AVMOp.mul, args=[selector, true])
            case 0, 1:
                zero_const = UInt64Constant(value=0, source_location=intrinsic.source_location)
                return attrs.evolve(intrinsic, op=AVMOp.neq, args=[selector, zero_const])
    elif intrinsic.op is AVMOp.replace2:
        (start,) = intrinsic.immediates
        assert isinstance(start, int)
        byte_arg_a, byte_arg_b = intrinsic.args
        if (byte_const_a := _get_byte_constant(register_assignments, byte_arg_a)) is not None and (
            byte_const_b := _get_byte_constant(register_assignments, byte_arg_b)
        ) is not None:
            folded_bytes = fold_replace2(byte_const_a.value, start, byte_const_b.value)
            if folded_bytes is not None:
                enc = choose_encoding(byte_const_a.encoding, byte_const_b.encoding)
                return models.BytesConstant(
                    value=folded_bytes, encoding=enc, source_location=op_loc
                )
    elif intrinsic.op is AVMOp.replace3:
        match intrinsic.args:
            case [
                models.Value(atype=AVMType.bytes) as byte_arg_a,
                models.UInt64Constant(value=start),
                models.Value(atype=AVMType.bytes) as byte_arg_b,
            ] if (
                (byte_const_a := _get_byte_constant(register_assignments, byte_arg_a)) is not None
                and (byte_const_b := _get_byte_constant(register_assignments, byte_arg_b))
                is not None
            ):
                folded_bytes = fold_replace2(byte_const_a.value, start, byte_const_b.value)
                if folded_bytes is not None:
                    enc = choose_encoding(byte_const_a.encoding, byte_const_b.encoding)
                    return models.BytesConstant(
                        value=folded_bytes, encoding=enc, source_location=op_loc
                    )
    # replace3 with a constant start arg ≤ 255 is converted to replace2 by
    # stack-to-immediate conversion (so the replace2 branch above handles it on a
    # subsequent pass); the replace3 branch directly above handles starts > 255 and
    # the pre-conversion case.
    elif intrinsic.op is AVMOp.getbit:
        match intrinsic.args:
            case [
                models.UInt64Constant(value=source, ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
            ]:
                if index < 64:
                    getbit_result = 1 if (source & (1 << index)) else 0
                    return models.UInt64Constant(value=getbit_result, source_location=op_loc)
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                folded = fold_getbit_bytes(byte_const.value, index)
                if folded is not None:
                    return models.UInt64Constant(value=folded, source_location=op_loc)
    elif intrinsic.op is AVMOp.getbyte:
        match intrinsic.args:
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                folded = fold_getbyte(byte_const.value, index)
                if folded is not None:
                    return models.UInt64Constant(value=folded, source_location=op_loc)
    elif intrinsic.op is AVMOp.setbit:
        match intrinsic.args:
            case [
                models.UInt64Constant(value=source, ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ]:
                folded = fold_setbit_uint64(source, index, value)
                if folded is not None:
                    return models.UInt64Constant(value=folded, source_location=op_loc)
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                folded_bytes = fold_setbit_bytes(byte_const.value, index, value)
                if folded_bytes is not None:
                    enc = chop_encoding(byte_const.encoding)
                    return models.BytesConstant(
                        value=folded_bytes, encoding=enc, source_location=op_loc
                    )
    elif intrinsic.op is AVMOp.setbyte:
        match intrinsic.args:
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                folded_bytes = fold_setbyte(byte_const.value, index, value)
                if folded_bytes is not None:
                    enc = chop_encoding(byte_const.encoding)
                    return models.BytesConstant(
                        value=folded_bytes, encoding=enc, source_location=op_loc
                    )
    elif intrinsic.op in EXTRACT_UINTN_BYTE_SIZE:
        match intrinsic.args:
            case [
                models.Value() as bytes_arg,
                models.UInt64Constant(value=offset),
            ] if (bytes_const := _get_byte_constant(register_assignments, bytes_arg)) is not None:
                folded = fold_extract_uint_n(intrinsic.op, bytes_const.value, offset)
                if folded is not None:
                    return models.UInt64Constant(value=folded, source_location=op_loc)
            case [
                models.Register() as bytes_arg,
                models.UInt64Constant(value=offset) as offset_const,
            ] if (bytes_arg_defn := register_assignments.get(bytes_arg)) is not None and (
                all(
                    isinstance(r, models.Assignment)
                    and isinstance(r.source, models.Intrinsic)
                    and r.source.op in EXTRACT_UINTN_BYTE_SIZE
                    for r in ssa_reads.get(bytes_arg)
                )
            ):
                # chained extract: extract_uint{N} (extract S 0 src) offset
                #     -> extract_uint{N} src (S + offset)
                match bytes_arg_defn.source:
                    case models.Intrinsic(
                        op=AVMOp.extract,
                        args=[src_bytes_arg],
                        immediates=[int(src_start), 0],
                    ):
                        new_offset = src_start + offset
                        if valid_uint64(new_offset):
                            new_offset_const = models.UInt64Constant(
                                value=new_offset,
                                source_location=offset_const.source_location,
                            )
                            return attrs.evolve(intrinsic, args=[src_bytes_arg, new_offset_const])
    elif intrinsic.op is AVMOp.concat:
        left_arg, right_arg = intrinsic.args
        left_const = _get_byte_constant(register_assignments, left_arg)
        right_const = _get_byte_constant(register_assignments, right_arg)
        if left_const is not None:
            if left_const.value == b"":
                return right_arg
            if right_const is not None:
                result_value = left_const.value + right_const.value
                if len(result_value) > algo_constants.MAX_BYTES_LENGTH:
                    return None  # would fail at runtime
                # two constants, just fold
                target_encoding = choose_encoding(
                    left_const.encoding, right_const.encoding, is_concat=True
                )
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
            ):
                byte_const = _get_byte_constant(register_assignments, byte_arg)
                if byte_const is not None:
                    # note there is a difference of behaviour between extract with stack args
                    # and with immediates - zero is to the end with immediates,
                    # and zero length with stacks
                    if len(byte_const.value) < S + L:
                        return None  # would fail at runtime
                    if intrinsic.immediates and L == 0:
                        extracted = byte_const.value[S:]
                    else:
                        extracted = byte_const.value[S : S + L]
                    enc = chop_encoding(byte_const.encoding)
                    return models.BytesConstant(
                        value=extracted, encoding=enc, source_location=op_loc
                    )
                elif (
                    (byte_arg_defn := register_assignments.get(byte_arg))
                    # don't do this optimisation for extract3 when the final argument is a constant
                    # zero, because of behaviour differences
                    and (intrinsic.immediates or L > 0)
                ):
                    match byte_arg_defn.source:
                        case models.Intrinsic(
                            op=AVMOp.extract, args=[src_bytes_arg], immediates=[int(src_start), 0]
                        ):
                            # only use extract variant if it is safe to do so
                            # (i.e. values are valid immediates)
                            if L < 256 and (S + src_start) < 256:
                                return models.Intrinsic(
                                    op=AVMOp.extract,
                                    args=[src_bytes_arg],
                                    immediates=[S + src_start, L],
                                    source_location=op_loc,
                                )
                            # only use extract3 if L is not 0 as that has special behaviour
                            elif L != 0:
                                # simplify a chained extract
                                return models.Intrinsic(
                                    # always use extract3, if possible it can be simplified to
                                    # extract by another optimization
                                    op=AVMOp.extract3,
                                    args=[
                                        src_bytes_arg,
                                        UInt64Constant(value=S + src_start, source_location=None),
                                        UInt64Constant(value=L, source_location=None),
                                    ],
                                    source_location=op_loc,
                                )
                            # else we cant safely optimize this
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
            ) if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                if S <= E <= len(byte_const.value):
                    extracted = byte_const.value[S:E]
                    enc = chop_encoding(byte_const.encoding)
                    return models.BytesConstant(
                        value=extracted, encoding=enc, source_location=op_loc
                    )
            case models.Intrinsic(
                args=[byte_arg, models.UInt64Constant(value=S), maybe_len_arg]
            ) if (
                (len_op := _get_len_op(register_assignments, maybe_len_arg))
                and len_op.args[0] == byte_arg
                and S <= 255
            ):
                return models.Intrinsic(
                    op=AVMOp.extract,
                    immediates=[S, 0],
                    args=[byte_arg],
                    source_location=intrinsic.source_location,
                )
    elif intrinsic.op is AVMOp.itob:
        (arg,) = intrinsic.args
        # TODO: expand to other extract sizes, but will need to pad result
        # extract_uint64 BYTES, START; itob -> extract3 BYTES, START, 8
        match register_assignments.get(arg):
            case models.Assignment(
                targets=[arg_reg],
                source=models.Intrinsic(
                    op=AVMOp.extract_uint64, args=[byte_arg, start_idx], immediates=[]
                ),
            ) if ssa_reads.count(arg_reg) == 1:
                assert arg_reg == arg
                return attrs.evolve(
                    intrinsic,
                    op=AVMOp.extract3,
                    args=[
                        byte_arg,
                        start_idx,
                        models.UInt64Constant(value=8, source_location=None),
                    ],
                )
    elif not intrinsic.immediates:
        match intrinsic.args:
            case [
                models.Value(atype=AVMType.uint64) as a,
                models.Value(atype=AVMType.uint64) as b,
            ]:
                return _try_simplify_uint64_binary_op(register_assignments, intrinsic, a, b)
            case [models.Value(atype=AVMType.bytes) as x]:
                return _try_simplify_bytes_unary_op(register_assignments, intrinsic, x)
            case [
                models.Value(atype=AVMType.bytes) as a,
                models.Value(atype=AVMType.bytes) as b,
            ]:
                return _try_simplify_bytes_binary_op(register_assignments, intrinsic, a, b)

    return None


def _get_len_op(
    register_assignments: _RegisterAssignments, maybe_len_reg: models.Value
) -> Intrinsic | None:
    ass = register_assignments.get(maybe_len_reg)
    if ass and isinstance(ass.source, models.Intrinsic) and ass.source.op == AVMOp.len_:
        return ass.source
    return None


_BinaryTripleSimplifier = Callable[
    [
        _RegisterAssignments,
        models.Intrinsic,
        tuple[models.Value, models.Value, models.Value],
        SourceLocation | None,
    ],
    models.Value | models.Intrinsic | None,
]


def _make_try_simplify_triple_uint64_math_commutative(
    op: AVMOp, reducer: Callable[[int, int], int]
) -> _BinaryTripleSimplifier:
    def simplifier(
        _: _RegisterAssignments,
        intrinsic: models.Intrinsic,
        args: tuple[models.Value, models.Value, models.Value],
        merged_loc: SourceLocation | None,
    ) -> models.Value | models.Intrinsic | None:
        assert intrinsic.op is op
        other = list[models.Value]()
        constants = list[int]()
        for arg in args:
            const_int = _get_int_constant(arg)
            if const_int is not None:
                constants.append(const_int)
            else:
                other.append(arg)
        match other:
            case [reg]:
                reduced = functools.reduce(reducer, constants)
                if not valid_uint64(reduced):
                    return None
                new_const = models.UInt64Constant(
                    value=reduced,
                    source_location=merged_loc,
                )
                return models.Intrinsic(
                    op=op,
                    args=[reg, new_const],
                    types=intrinsic.types,
                    source_location=merged_loc,
                )
            case _:
                return None

    return simplifier


def _make_try_simplify_triple_bytes_math_commutative(
    op: AVMOp, reducer: Callable[[int, int], int]
) -> _BinaryTripleSimplifier:
    def simplifier(
        register_assignments: _RegisterAssignments,
        intrinsic: models.Intrinsic,
        args: tuple[models.Value, models.Value, models.Value],
        merged_loc: SourceLocation | None,
    ) -> models.Value | models.Intrinsic | None:
        assert intrinsic.op is op
        other = list[models.Value]()
        constants = list[int]()
        for arg in args:
            const_bigint, _ = _get_biguint_constant(register_assignments, arg)
            if const_bigint is not None:
                constants.append(const_bigint)
            else:
                other.append(arg)
        match other:
            case [reg]:
                new_big_const = models.BigUIntConstant(
                    value=functools.reduce(reducer, constants),
                    source_location=merged_loc,
                )
                return models.Intrinsic(
                    op=op,
                    args=[reg, new_big_const],
                    types=intrinsic.types,
                    source_location=merged_loc,
                )
            case _:
                return None

    return simplifier


def _try_normalise_bytes_constant(maybe_byte_arg: models.Value) -> models.Value:
    # TODO: may want to consider looking up register assignments at O2
    if isinstance(maybe_byte_arg, models.Constant):
        maybe_normed = _normalise_bytes_constant(maybe_byte_arg)
        if maybe_normed is not None:
            return maybe_normed
    return maybe_byte_arg


def _try_simplify_triple_concat(
    _: _RegisterAssignments,
    intrinsic: models.Intrinsic,
    args: tuple[models.Value, models.Value, models.Value],
    merged_loc: SourceLocation | None,
) -> models.Value | models.Intrinsic | None:
    assert intrinsic.op is AVMOp.concat
    normalised_args = list(map(_try_normalise_bytes_constant, args))
    match normalised_args:
        case (
            models.Value() as reg,
            models.BytesConstant() as bytes_const1,
            models.BytesConstant() as bytes_const2,
        ):
            new_const_value = bytes_const1.value + bytes_const2.value
            if len(new_const_value) > algo_constants.MAX_BYTES_LENGTH:
                return None  # would fail at runtime
            target_encoding = choose_encoding(
                bytes_const1.encoding, bytes_const2.encoding, is_concat=True
            )
            new_byte_const = models.BytesConstant(
                value=new_const_value,
                encoding=target_encoding,
                source_location=merged_loc,
            )
            return models.Intrinsic(
                op=AVMOp.concat,
                args=[reg, new_byte_const],
                types=intrinsic.types,
                source_location=merged_loc,
            )
        case (
            models.BytesConstant() as bytes_const1,
            models.BytesConstant() as bytes_const2,
            models.Value() as reg,
        ):
            new_const_value = bytes_const1.value + bytes_const2.value
            if len(new_const_value) > algo_constants.MAX_BYTES_LENGTH:
                return None  # would fail at runtime
            target_encoding = choose_encoding(
                bytes_const1.encoding, bytes_const2.encoding, is_concat=True
            )
            new_byte_const = models.BytesConstant(
                value=new_const_value,
                encoding=target_encoding,
                source_location=merged_loc,
            )
            return models.Intrinsic(
                op=AVMOp.concat,
                args=[new_byte_const, reg],
                types=intrinsic.types,
                source_location=merged_loc,
            )
    return None


_BINARY_TRIPLE_SIMPLIFIER: typing.Final[Mapping[AVMOp, _BinaryTripleSimplifier]] = {
    AVMOp.concat: _try_simplify_triple_concat,
    AVMOp.add: _make_try_simplify_triple_uint64_math_commutative(AVMOp.add, operator.add),
    AVMOp.mul: _make_try_simplify_triple_uint64_math_commutative(AVMOp.mul, operator.mul),
    AVMOp.bitwise_and: _make_try_simplify_triple_uint64_math_commutative(
        AVMOp.bitwise_and, operator.and_
    ),
    AVMOp.bitwise_or: _make_try_simplify_triple_uint64_math_commutative(
        AVMOp.bitwise_or, operator.or_
    ),
    AVMOp.bitwise_xor: _make_try_simplify_triple_uint64_math_commutative(
        AVMOp.bitwise_xor, operator.xor
    ),
    AVMOp.add_bytes: _make_try_simplify_triple_bytes_math_commutative(
        AVMOp.add_bytes, operator.add
    ),
    AVMOp.mul_bytes: _make_try_simplify_triple_bytes_math_commutative(
        AVMOp.mul_bytes, operator.mul
    ),
}


def _try_simplify_repeated_binary_op(
    register_assignments: _RegisterAssignments,
    ass: models.Assignment,
    intrinsic: models.Intrinsic,
    ssa_reads: SSAReadTracker,
) -> models.Value | models.Intrinsic | None:
    assert ass.source is intrinsic

    # this implicitly checks that it's a binary op
    simplifier = _BINARY_TRIPLE_SIMPLIFIER.get(intrinsic.op)
    if simplifier is None:
        return None
    left, right = intrinsic.args
    # check to see if either/both arguments are only used by `intrinsic`
    expand_left: models.Register | None = None
    expand_right: models.Register | None = None
    if isinstance(left, models.Register) and ssa_reads.is_sole_usage(left, ass):
        expand_left = left
    if isinstance(right, models.Register) and ssa_reads.is_sole_usage(right, ass):
        expand_right = right

    if expand_left is not None:
        # check to see if the register argument is itself the result of an intrinsic with two args
        match register_assignments.get(expand_left):
            case models.Assignment(
                targets=[sole_target],
                source=models.Intrinsic(args=[left1, left2]) as reg_intrinsic,
            ) if reg_intrinsic.op == intrinsic.op:
                assert sole_target == expand_left
                merged_loc = sequential_source_locations_merge(
                    (intrinsic.source_location, reg_intrinsic.source_location)
                )
                maybe_simplified = simplifier(
                    register_assignments, intrinsic, (left1, left2, right), merged_loc
                )
                if maybe_simplified is not None:
                    return maybe_simplified

    if expand_right is not None:
        # check to see if the register argument is itself the result of an intrinsic with two args
        match register_assignments.get(expand_right):
            case models.Assignment(
                targets=[sole_target],
                source=models.Intrinsic(args=[right1, right2]) as reg_intrinsic,
            ) if reg_intrinsic.op == intrinsic.op:
                assert sole_target == expand_right
                merged_loc = sequential_source_locations_merge(
                    (intrinsic.source_location, reg_intrinsic.source_location)
                )
                return simplifier(
                    register_assignments, intrinsic, (left, right1, right2), merged_loc
                )
    return None


def _get_int_constant(value: models.Value) -> int | None:
    if isinstance(value, models.UInt64Constant):
        return value.value
    return None


def _get_biguint_constant(
    register_assignments: _RegisterAssignments, value: models.Value
) -> tuple[int | None, models.BytesConstant] | tuple[None, None]:
    if isinstance(value, models.BigUIntConstant):
        biguint_byte_const = _biguint_constant_to_bytes_constant(value)
        if len(biguint_byte_const.value) <= 64:
            return value.value, biguint_byte_const
        else:
            return None, biguint_byte_const
    byte_const = _get_byte_constant(register_assignments, value)
    if byte_const is None:
        return None, byte_const
    biguint_value = None
    if len(byte_const.value) <= 64:
        biguint_value = int.from_bytes(byte_const.value, byteorder="big", signed=False)
    return biguint_value, byte_const


def _get_byte_constant(
    register_assignments: _RegisterAssignments, byte_arg: models.Value
) -> models.BytesConstant | None:
    if byte_arg_defn := register_assignments.get(byte_arg):
        match byte_arg_defn.source:
            case models.Intrinsic(op=AVMOp.itob, args=[models.UInt64Constant(value=itob_arg)]):
                return _eval_itob(itob_arg, byte_arg_defn.source_location)
            case models.Intrinsic(op=AVMOp.bzero, args=[models.UInt64Constant(value=bzero_arg)]):
                return _eval_bzero(bzero_arg, byte_arg_defn.source_location)
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                return models.BytesConstant(
                    value=Address.parse(algo_constants.ZERO_ADDRESS).public_key,
                    encoding=AVMBytesEncoding.base32,
                    source_location=byte_arg.source_location,
                )
    elif isinstance(byte_arg, models.Constant):
        return _normalise_bytes_constant(byte_arg)
    return None


def _normalise_bytes_constant(byte_arg: models.Constant) -> models.BytesConstant | None:
    if type(byte_arg) is models.BytesConstant:
        return byte_arg
    maybe_const_value = get_bytes_constant(byte_arg)
    if maybe_const_value is not None:
        encoding = (
            AVMBytesEncoding.base32
            if byte_arg.ir_type == PrimitiveIRType.account
            else AVMBytesEncoding.base16
        )
        return models.BytesConstant(
            value=maybe_const_value,
            encoding=encoding,
            source_location=byte_arg.source_location,
        )
    return None


def _get_bytes_length_safe(
    register_assignments: _RegisterAssignments, byte_arg: models.Value
) -> int | None:
    assert byte_arg.atype is AVMType.bytes
    if byte_arg_defn := register_assignments.get(byte_arg):
        if isinstance(byte_arg_defn.source, models.Intrinsic):
            # TODO: could expand this to e.g. substring, bzero with additional testing
            if byte_arg_defn.source.op is AVMOp.extract:
                start, length = byte_arg_defn.source.immediates
                assert isinstance(length, int)
                if length != 0:
                    # verify the source is long enough for this extract
                    (source_arg,) = byte_arg_defn.source.args
                    source_len = _get_bytes_length_safe(register_assignments, source_arg)
                    assert isinstance(start, int)
                    if source_len is not None and (start + length) <= source_len:
                        # only trust the extract length if we trust the source size
                        return length
                return None
            (return_ir_type,) = byte_arg_defn.source.op_signature.returns
            return return_ir_type.num_bytes
        if isinstance(byte_arg_defn.source, models.InnerTransactionField):
            return byte_arg_defn.source.type.num_bytes
    elif isinstance(byte_arg, models.BigUIntConstant):
        return biguint_bytes_length(byte_arg.value)
    elif isinstance(byte_arg, models.Constant):
        return byte_arg.ir_type.num_bytes
    return None


def _biguint_constant_to_bytes_constant(const: models.BigUIntConstant) -> models.BytesConstant:
    return models.BytesConstant(
        value=biguint_bytes_eval(const.value),
        encoding=AVMBytesEncoding.base16,
        source_location=const.source_location,
    )


def _eval_itob(arg: int, loc: SourceLocation | None) -> models.BytesConstant:
    return models.BytesConstant(
        value=arg.to_bytes(8, byteorder="big", signed=False),
        encoding=AVMBytesEncoding.base16,
        source_location=loc,
    )


def _eval_bzero(arg: int, loc: SourceLocation | None) -> models.BytesConstant | None:
    if arg <= 64:
        return models.BytesConstant(
            value=b"\x00" * arg,
            encoding=AVMBytesEncoding.base16,
            source_location=loc,
        )
    return None


_EXTRACT_UINT_OPS_BY_LENGTH = {
    1: AVMOp.getbyte,
    **{v: k for k, v in EXTRACT_UINTN_BYTE_SIZE.items()},
}


def _try_simplify_bytes_unary_op(
    register_assignments: _RegisterAssignments, intrinsic: models.Intrinsic, arg: models.Value
) -> models.Value | models.Intrinsic | None:
    op_loc = intrinsic.source_location
    op = intrinsic.op
    if (
        op is AVMOp.len_
        and (safe_num_bytes := _get_bytes_length_safe(register_assignments, arg)) is not None
    ):
        return models.UInt64Constant(value=safe_num_bytes, source_location=op_loc)
    if op is AVMOp.btoi and (arg_defn := register_assignments.get(arg)):
        match arg_defn.source:
            # extract* BYTES, START, LEN; btoi -> extract_uint* BYTES, START
            case models.Intrinsic(
                op=AVMOp.extract, args=[bites], immediates=[int(start), int(length)]
            ) if length in _EXTRACT_UINT_OPS_BY_LENGTH:
                return attrs.evolve(
                    intrinsic,
                    op=_EXTRACT_UINT_OPS_BY_LENGTH[length],
                    args=[bites, UInt64Constant(value=start, source_location=None)],
                )
            case models.Intrinsic(
                op=AVMOp.extract3,
                args=[bites, start_arg, models.UInt64Constant(value=length)],
            ) if length in _EXTRACT_UINT_OPS_BY_LENGTH:
                return attrs.evolve(
                    intrinsic,
                    op=_EXTRACT_UINT_OPS_BY_LENGTH[length],
                    args=[bites, start_arg],
                )
    return None


def _try_simplify_uint64_binary_op(
    register_assignments: _RegisterAssignments,
    intrinsic: models.Intrinsic,
    a: models.Value,
    b: models.Value,
    *,
    bool_context: bool = False,
) -> models.Value | models.Intrinsic | None:
    op = intrinsic.op
    a_const = _get_int_constant(a)
    b_const = _get_int_constant(b)
    if a_const is not None or b_const is not None:
        if op == AVMOp.eq:
            if a_const == 0:
                return attrs.evolve(intrinsic, op=AVMOp.not_, args=[b])
            if b_const == 0:
                return attrs.evolve(intrinsic, op=AVMOp.not_, args=[a])
        if bool_context:
            match simplify_uint64_binary_op_one_const(
                op, a, b, a_const, b_const, bool_context=True
            ):
                case int(c):
                    (ir_type,) = intrinsic.types
                    return models.UInt64Constant(
                        value=c, ir_type=ir_type, source_location=intrinsic.source_location
                    )
                case BinarySimplification.LEFT:
                    return a
                case BinarySimplification.RIGHT:
                    return b
                case default:
                    typing.assert_type(default, None)
    if op in (AVMOp.and_, AVMOp.or_):
        new_a = _try_simplify_bool_condition(register_assignments, a) or a
        new_b = _try_simplify_bool_condition(register_assignments, b) or b
        if new_a is not a or new_b is not b:
            return attrs.evolve(intrinsic, args=[new_a, new_b])
    return None


def _wrap_biguint_or_uint64(c: int, intrinsic: models.Intrinsic) -> models.Value:
    (ir_type,) = intrinsic.types
    if ir_type == PrimitiveIRType.biguint:
        return models.BigUIntConstant(value=c, source_location=intrinsic.source_location)
    assert ir_type.avm_type is AVMType.uint64
    return models.UInt64Constant(
        value=c, ir_type=ir_type, source_location=intrinsic.source_location
    )


def _try_simplify_bytes_binary_op(
    register_assignments: _RegisterAssignments,
    intrinsic: models.Intrinsic,
    a: models.Value,
    b: models.Value,
) -> models.Value | None:
    op = intrinsic.op
    # a_const, a_const_bytes = _get_biguint_constant(register_assignments, a)
    # b_const, b_const_bytes = _get_biguint_constant(register_assignments, b)
    # if (
    #     a_const is not None
    #     and b_const is not None
    #     and (folded := fold_biguint_const_binary_op(op, a_const, b_const)) is not None
    # ):
    #     return _wrap_biguint_or_uint64(folded, intrinsic)
    # if a_const_bytes is not None and b_const_bytes is not None:
    #     match fold_bytes_const_binary_op(op, a_const_bytes.value, b_const_bytes.value):
    #         case int(v):
    #             return _wrap_biguint_or_uint64(v, intrinsic)
    #         case bytes(result_bytes):
    #             return models.BytesConstant(
    #                 value=result_bytes,
    #                 encoding=choose_encoding(a_const_bytes.encoding, b_const_bytes.encoding),
    #                 source_location=intrinsic.source_location,
    #             )
    #         case None:
    #             pass
    #         case unexpected:
    #             typing.assert_never(unexpected)
    #
    # match simplify_bytes_binary_op_one_const(op, a_const, b_const):
    #     case int(v):
    #         return _wrap_biguint_or_uint64(v, intrinsic)
    #     case BinarySimplification.LEFT:
    #         return a
    #     case BinarySimplification.RIGHT:
    #         return b
    #     case other:
    #         typing.assert_type(other, None)

    a_size = _get_bytes_length_safe(register_assignments, a)
    b_size = _get_bytes_length_safe(register_assignments, b)
    if a_size is not None and b_size is not None and a_size != b_size:
        if op is AVMOp.eq:
            return _wrap_biguint_or_uint64(0, intrinsic)
        if op is AVMOp.neq:
            return _wrap_biguint_or_uint64(1, intrinsic)
    return None
