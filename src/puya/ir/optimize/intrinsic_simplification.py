import contextlib
import functools
import hashlib
import math
import operator
import typing
from collections import defaultdict, deque
from collections.abc import Callable, Container, Generator, Iterable, Mapping, Set
from itertools import zip_longest

import attrs

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import models
from puya.ir._utils import get_bytes_constant
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Intrinsic, UInt64Constant
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.optimize.dead_code_elimination import SIDE_EFFECT_FREE_AVM_OPS
from puya.ir.register_read_collector import RegisterReadCollector
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import Address, biguint_bytes_eval, biguint_bytes_length, set_add, sha512_256_hash

logger = log.get_logger(__name__)


_AnyOp = models.Op | models.ControlOp | models.Phi

_RegisterAssignments = Mapping[models.Value, models.Assignment]

COMPILE_TIME_CONSTANT_OPS = frozenset(
    [
        # "generic" comparison ops
        "==",
        "!=",
        # uint64 comparison ops
        "<",
        "<=",
        ">",
        ">=",
        # boolean ops
        "!",
        "&&",
        "||",
        # uint64 bitwise ops
        "&",
        "|",
        "^",
        "~",
        "shl",
        "shr",
        # uint64 math
        "+",
        "-",
        "*",
        "/",
        "%",
        "exp",
        "sqrt",
        # wide math
        "addw",
        "mulw",
        "divw",
        "expw",
        "divmodw",
        # bit/byte ops
        "concat",
        "extract",
        "extract3",
        "getbit",
        "getbyte",
        "len",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "substring",
        "substring3",
        # conversion
        "itob",
        "btoi",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        # byte math
        "b+",
        "b-",
        "b*",
        "b/",
        "b%",
        "bsqrt",
        # byte comaprison ops
        "b==",
        "b!=",
        "b<",
        "b<=",
        "b>",
        "b>=",
        # byte bitwise ops
        "b&",
        "b|",
        "b^",
        "b~",
        # misc
        "assert",
        "bzero",
        "select",
        "bitlen",
        # ! unimplemented for constant arg evaluation
        "base64_decode",
        "ec_add",
        "ec_map_to",
        "ec_multi_scalar_mul",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "json_ref",
        "keccak256",
        "sha256",
        "sha3_256",
        "sha512_256",
        "vrf_verify",
        "sumhash512",  # AVM 11
    ]
)


def intrinsic_simplifier(context: IROptimizationContext, subroutine: models.Subroutine) -> bool:
    work_list = _AssignmentWorkQueue(COMPILE_TIME_CONSTANT_OPS)
    ssa_reads = _SSAReadTracker()

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
                    models.Assignment(source=models.Intrinsic() as intrinsic) as ass
                ) if intrinsic.args:
                    with_immediates = _try_convert_stack_args_to_immediates(intrinsic)
                    if with_immediates is not None:
                        logger.debug(f"Simplified {op.source} to {with_immediates}")
                        op.source = with_immediates
                        modified += 1
                    elif intrinsic.op == AVMOp.box_get:
                        maybe_value, exists = ass.targets
                        if ssa_reads.count(maybe_value) == 0:
                            logger.debug(
                                f"replacing box_get with box_len"
                                f" because {maybe_value.local_id} is unused"
                            )
                            modified += 1
                            # we've checked this isn't used, so it's safe to just change it's type
                            ass.targets[0] = attrs.evolve(
                                maybe_value, ir_type=PrimitiveIRType.uint64
                            )
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
            isinstance(op.source, models.Intrinsic)
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


@attrs.frozen
class _SSAReadTracker:
    _data: defaultdict[models.Register, set[_AnyOp]] = attrs.field(
        factory=lambda: defaultdict(set), init=False
    )

    def add(self, op: _AnyOp) -> None:
        for read_reg in self._register_reads(op):
            self._data[read_reg].add(op)

    def get(self, reg: models.Register, *, copy: bool = False) -> Iterable[_AnyOp]:
        reads = self._data.get(reg)
        if reads is None:
            return ()
        if copy:
            return reads.copy()
        return reads

    def count(self, reg: models.Register) -> int:
        reads = self._data.get(reg)
        if reads is None:
            return 0
        return len(reads)

    def is_sole_usage(self, reg: models.Register, op: _AnyOp) -> bool:
        try:
            (sole_usage,) = self._data[reg]
        except (KeyError, ValueError):
            return False
        else:
            return sole_usage is op

    @contextlib.contextmanager
    def update(self, op: _AnyOp) -> Generator[None, None, None]:
        old_reads = self._register_reads(op)
        yield
        new_reads = self._register_reads(op)
        for removed_read in old_reads - new_reads:
            self._data[removed_read].remove(op)
        for added_read in new_reads - old_reads:
            self._data[added_read].add(op)

    @staticmethod
    def _register_reads(visitable: models.IRVisitable) -> Set[models.Register]:
        collector = RegisterReadCollector()
        visitable.accept(collector)
        return collector.used_registers


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
        ops = []
        for op in block.ops:
            if not isinstance(op, models.Intrinsic):
                ops.append(op)
            else:
                result = _visit_intrinsic_op(op, register_intrinsics)
                if result is not op:
                    modified += 1
                if result is not None:
                    ops.append(result)
        block.ops[:] = ops
    return modified


def _visit_intrinsic_op(
    intrinsic: Intrinsic, register_intrinsics: Mapping[models.Value, models.Intrinsic]
) -> Intrinsic | None:
    # if we get here, it means either the intrinsic doesn't have a return or it's ignored,
    # in either case, the result has to be either an Op or None (ie delete),
    # so we don't invoke _try_fold_intrinsic here
    if intrinsic.op == AVMOp.assert_:
        (cond,) = intrinsic.args
        if isinstance(cond, models.UInt64Constant):
            value = cond.value
            if value:
                return None
            else:
                # an assert 0 could be simplified to an err, but
                # this would make it a ControlOp, so the block would
                # need to be restructured
                pass
        elif cond_op := register_intrinsics.get(cond):
            assert_cond_maybe_simplified = _try_simplify_bool_intrinsic(cond_op)
            if assert_cond_maybe_simplified is not None:
                return attrs.evolve(intrinsic, args=[assert_cond_maybe_simplified])
        return intrinsic
    elif intrinsic.op == AVMOp.itxn_field:
        (field_im,) = intrinsic.immediates
        if field_im in ("ApprovalProgramPages", "ClearStateProgramPages"):
            (page_value,) = intrinsic.args
            if isinstance(page_value, models.BytesConstant) and page_value.value == b"":
                return None
        return intrinsic
    elif intrinsic.op.code in SIDE_EFFECT_FREE_AVM_OPS:
        logger.debug(f"Removing unused pure op {intrinsic}")
        return None
    elif intrinsic.args:
        simplified = _try_convert_stack_args_to_immediates(intrinsic)
        if simplified is not None:
            return simplified
        else:
            return intrinsic
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
    context: IROptimizationContext,
    ssa_reads: _SSAReadTracker,
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
            replaced = bytearray(byte_const_a.value)
            replaced[start : start + len(byte_const_b.value)] = byte_const_b.value
            return models.BytesConstant(
                value=bytes(replaced),
                encoding=_choose_encoding(byte_const_a.encoding, byte_const_b.encoding),
                source_location=op_loc,
            )
    elif intrinsic.op is AVMOp.replace3:
        byte_arg_a, start_s, byte_arg_b = intrinsic.args
        if (
            (start2 := _get_int_constant(start_s)) is not None
            and (byte_const_a := _get_byte_constant(register_assignments, byte_arg_a)) is not None
            and (byte_const_b := _get_byte_constant(register_assignments, byte_arg_b)) is not None
        ):
            replaced = bytearray(byte_const_a.value)
            replaced[start2 : start2 + len(byte_const_b.value)] = byte_const_b.value
            return models.BytesConstant(
                value=bytes(replaced),
                encoding=_choose_encoding(byte_const_a.encoding, byte_const_b.encoding),
                source_location=op_loc,
            )
    elif intrinsic.op is AVMOp.getbit:
        match intrinsic.args:
            case [
                models.UInt64Constant(value=source, ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
            ]:
                getbit_result = 1 if (source & (1 << index)) else 0
                return models.UInt64Constant(value=getbit_result, source_location=op_loc)
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
                binary_array = [
                    x for xs in [bin(bb)[2:].zfill(8) for bb in byte_const.value] for x in xs
                ]
                the_bit = binary_array[index]
                return models.UInt64Constant(source_location=op_loc, value=int(the_bit))
    elif intrinsic.op is AVMOp.setbit:
        match intrinsic.args:
            case [
                models.UInt64Constant(value=source, ir_type=PrimitiveIRType.uint64),
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ]:
                if value:
                    setbit_result = source | (1 << index)
                else:
                    setbit_result = source & ~(1 << index)
                return models.UInt64Constant(value=setbit_result, source_location=op_loc)
            case [
                models.Value(atype=AVMType.bytes) as byte_arg,
                models.UInt64Constant(value=index),
                models.UInt64Constant(value=value),
            ] if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
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
    elif intrinsic.op.code.startswith("extract_uint"):
        match intrinsic.args:
            case [
                models.Value() as bytes_arg,
                models.UInt64Constant(value=offset),
            ] if (bytes_const := _get_byte_constant(register_assignments, bytes_arg)) is not None:
                bytes_value = bytes_const.value
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
        left_const = _get_byte_constant(register_assignments, left_arg)
        right_const = _get_byte_constant(register_assignments, right_arg)
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
            ):
                byte_const = _get_byte_constant(register_assignments, byte_arg)
                if byte_const is not None:
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
                if E < S:
                    return None  # would fail at runtime, lets hope this is unreachable 😬
                extracted = byte_const.value[S:E]
                return models.BytesConstant(
                    source_location=op_loc, encoding=byte_const.encoding, value=extracted
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
    elif not intrinsic.immediates:
        match intrinsic.args:
            case [models.Value(atype=AVMType.uint64) as x]:
                return _try_simplify_uint64_unary_op(
                    context, ssa_reads, register_assignments, intrinsic, x
                )
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
        # TODO: maybe consider overflow? we don't consider in binary simplification..
        match other:
            case []:
                return models.UInt64Constant(
                    value=functools.reduce(reducer, constants),
                    source_location=merged_loc,
                    # TODO: types?
                )
            case [reg]:
                new_const = models.UInt64Constant(
                    value=functools.reduce(reducer, constants),
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
        # TODO: maybe consider overflow? we don't consider in binary simplification..
        match other:
            case []:
                return models.BigUIntConstant(
                    value=functools.reduce(reducer, constants),
                    source_location=merged_loc,
                    # TODO: types?
                )
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
            target_encoding = _choose_encoding(bytes_const1.encoding, bytes_const2.encoding)
            new_const_value = bytes_const1.value + bytes_const2.value
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
            target_encoding = _choose_encoding(bytes_const1.encoding, bytes_const2.encoding)
            new_const_value = bytes_const1.value + bytes_const2.value
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
    ssa_reads: _SSAReadTracker,
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
        return value.value, _biguint_constant_to_bytes_constant(value)
    byte_const = _get_byte_constant(register_assignments, value)
    if byte_const is None:
        return None, byte_const
    biguint_value = None
    if len(byte_const.value) <= 64:
        biguint_value = int.from_bytes(byte_const.value, byteorder="big", signed=False)
    return biguint_value, byte_const


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


def _eval_sha256(arg: bytes, loc: SourceLocation | None) -> models.BytesConstant:
    return models.BytesConstant(
        value=hashlib.sha256(arg).digest(),
        encoding=AVMBytesEncoding.base16,
        source_location=loc,
    )


def _eval_sha3_256(arg: bytes, loc: SourceLocation | None) -> models.BytesConstant:
    return models.BytesConstant(
        value=hashlib.sha3_256(arg).digest(),
        encoding=AVMBytesEncoding.base16,
        source_location=loc,
    )


def _eval_sha512_256(arg: bytes, loc: SourceLocation | None) -> models.BytesConstant:
    return models.BytesConstant(
        value=sha512_256_hash(arg),
        encoding=AVMBytesEncoding.base16,
        source_location=loc,
    )


def _eval_keccak256(arg: bytes, loc: SourceLocation | None) -> models.BytesConstant:
    from Cryptodome.Hash import keccak

    return models.BytesConstant(
        value=keccak.new(data=arg, digest_bits=256).digest(),
        encoding=AVMBytesEncoding.base16,
        source_location=loc,
    )


def _try_simplify_uint64_unary_op(
    context: IROptimizationContext,
    ssa_reads: _SSAReadTracker,
    register_assignments: _RegisterAssignments,
    intrinsic: models.Intrinsic,
    arg: models.Value,
) -> models.Value | models.Intrinsic | None:
    op_loc = intrinsic.source_location

    if intrinsic.op is AVMOp.itob:
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
        elif intrinsic.op is AVMOp.bitlen:
            return UInt64Constant(value=x.bit_length(), source_location=op_loc)
        elif intrinsic.op is AVMOp.itob:
            if context.expand_all_bytes:
                return _eval_itob(x, op_loc)
        elif intrinsic.op is AVMOp.bzero:
            if context.expand_all_bytes:
                return _eval_bzero(x, op_loc)
        else:
            logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {x}")

    return None


_EXTRACT_UINT_OPS_BY_LENGTH = {
    1: AVMOp.getbyte,
    2: AVMOp.extract_uint16,
    4: AVMOp.extract_uint32,
    8: AVMOp.extract_uint64,
}


def _try_simplify_bytes_unary_op(
    register_assignments: _RegisterAssignments, intrinsic: models.Intrinsic, arg: models.Value
) -> models.Value | models.Intrinsic | None:
    op_loc = intrinsic.source_location
    if intrinsic.op is AVMOp.bsqrt:
        biguint_const, _ = _get_biguint_constant(register_assignments, arg)
        if biguint_const is not None:
            value = math.isqrt(biguint_const)
            return models.BigUIntConstant(value=value, source_location=op_loc)
    if (
        intrinsic.op is AVMOp.len_
        and (safe_num_bytes := _get_bytes_length_safe(register_assignments, arg)) is not None
    ):
        return models.UInt64Constant(value=safe_num_bytes, source_location=op_loc)
    else:
        byte_const = _get_byte_constant(register_assignments, arg)
        if byte_const is not None:
            if intrinsic.op is AVMOp.bitwise_not_bytes:
                inverted = bytes([x ^ 0xFF for x in byte_const.value])
                return models.BytesConstant(
                    value=inverted, encoding=byte_const.encoding, source_location=op_loc
                )
            elif (
                intrinsic.op is AVMOp.btoi
                and len(byte_const.value) <= 8  # don't produce invalid values when optimizing
            ):
                converted = int.from_bytes(byte_const.value, byteorder="big", signed=False)
                return models.UInt64Constant(value=converted, source_location=op_loc)
            elif intrinsic.op is AVMOp.sha256:
                return _eval_sha256(byte_const.value, op_loc)
            elif intrinsic.op is AVMOp.sha3_256:
                return _eval_sha3_256(byte_const.value, op_loc)
            elif intrinsic.op is AVMOp.sha512_256:
                return _eval_sha512_256(byte_const.value, op_loc)
            elif intrinsic.op is AVMOp.keccak256:
                return _eval_keccak256(byte_const.value, op_loc)
            elif intrinsic.op is AVMOp.len_:
                length = len(byte_const.value)
                return models.UInt64Constant(value=length, source_location=op_loc)
            elif intrinsic.op is AVMOp.bitlen:
                converted = int.from_bytes(byte_const.value, byteorder="big", signed=False)
                return UInt64Constant(value=converted.bit_length(), source_location=op_loc)
            else:
                logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {byte_const}")
        elif intrinsic.op is AVMOp.btoi and (arg_defn := register_assignments.get(arg)):
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
                # btoi(itob(x)) = x
                case models.Intrinsic(op=AVMOp.itob, args=[source_uint64], immediates=[]):
                    return source_uint64
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

        # a >= 0 <-> 1
        if b_const == 0 and op == AVMOp.gte:  # noqa: SIM114
            c = 1
        # 0 <= b <-> 1
        elif a_const == 0 and op == AVMOp.lte:
            c = 1
        elif a_const == 1 and op == AVMOp.mul:
            c = b
        elif b_const == 1 and op in (AVMOp.mul, AVMOp.div_floor):
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
        #   OR
        # 1 <= b <-> b
        elif (bool_context or b.ir_type == PrimitiveIRType.bool) and (
            (a_const == 0 and op in (AVMOp.neq, AVMOp.lt)) or (a_const == 1 and op == AVMOp.lte)
        ):
            c = b
        # a != 0 <-> a
        #   OR
        # a > 0 <-> a
        #   OR
        # a >= 1 <-> a
        elif (bool_context or a.ir_type == PrimitiveIRType.bool) and (
            (b_const == 0 and op in (AVMOp.neq, AVMOp.gt)) or (b_const == 1 and op == AVMOp.gte)
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
        # 0 == b <-> !b
        elif a_const == 0 and op == AVMOp.eq:
            return attrs.evolve(intrinsic, op=AVMOp.not_, args=[b])
        # a == 0 <-> !a
        elif b_const == 0 and op == AVMOp.eq:
            return attrs.evolve(intrinsic, op=AVMOp.not_, args=[a])
    if c is None and op in (AVMOp.and_, AVMOp.or_):
        new_a = _try_simplify_bool_condition(register_assignments, a) or a
        new_b = _try_simplify_bool_condition(register_assignments, b) or b
        if new_a is not a or new_b is not b:
            return attrs.evolve(intrinsic, args=[new_a, new_b])
    if not isinstance(c, int):
        return c
    if c < 0:
        # Value cannot be folded as it would result in a negative uint64
        # TODO: what about overflow?
        return None
    return models.UInt64Constant(value=c, source_location=intrinsic.source_location)


def _try_simplify_bytes_binary_op(
    register_assignments: _RegisterAssignments,
    intrinsic: models.Intrinsic,
    a: models.Value,
    b: models.Value,
) -> models.Value | None:
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
        a_const, a_const_bytes = _get_biguint_constant(register_assignments, a)
        b_const, b_const_bytes = _get_biguint_constant(register_assignments, b)
        if a_const == 1 and op == AVMOp.mul_bytes:
            c = b
        elif b_const == 1 and op in (AVMOp.mul_bytes, AVMOp.div_floor_bytes):
            c = a
        elif a_const == 0 and op == AVMOp.add_bytes:
            c = b
        elif b_const == 0 and op in (AVMOp.add_bytes, AVMOp.sub_bytes):
            c = a
        elif 0 in (a_const, b_const) and op == AVMOp.mul_bytes:
            c = 0
        else:
            if a_const is not None and b_const is not None:
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
            if c is None and (a_const_bytes is not None and b_const_bytes is not None):
                match op:
                    case AVMOp.eq:
                        c = 1 if a_const_bytes.value == b_const_bytes.value else 0
                    case AVMOp.neq:
                        c = 1 if a_const_bytes.value != b_const_bytes.value else 0
                    case AVMOp.bitwise_or_bytes:
                        return models.BytesConstant(
                            value=_byte_wise(
                                operator.or_, a_const_bytes.value, b_const_bytes.value
                            ),
                            encoding=_choose_encoding(
                                a_const_bytes.encoding, b_const_bytes.encoding
                            ),
                            source_location=op_loc,
                        )
                    case AVMOp.bitwise_and_bytes:
                        return models.BytesConstant(
                            value=_byte_wise(
                                operator.and_, a_const_bytes.value, b_const_bytes.value
                            ),
                            encoding=_choose_encoding(
                                a_const_bytes.encoding, b_const_bytes.encoding
                            ),
                            source_location=op_loc,
                        )
                    case AVMOp.bitwise_xor_bytes:
                        return models.BytesConstant(
                            value=_byte_wise(
                                operator.xor, a_const_bytes.value, b_const_bytes.value
                            ),
                            encoding=_choose_encoding(
                                a_const_bytes.encoding, b_const_bytes.encoding
                            ),
                            source_location=op_loc,
                        )
            if c is None:
                a_size = _get_bytes_length_safe(register_assignments, a)
                b_size = _get_bytes_length_safe(register_assignments, b)
                if a_size is not None and b_size is not None and a_size != b_size:
                    if op is AVMOp.eq:
                        c = 0
                    elif op is AVMOp.neq:
                        c = 1
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
