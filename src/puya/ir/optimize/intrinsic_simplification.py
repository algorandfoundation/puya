import base64
import contextlib
import hashlib
import math
import operator
import typing
from collections import defaultdict, deque
from collections.abc import Callable, Container, Generator, Iterable, Mapping, Sequence, Set
from itertools import zip_longest

import attrs

from puya import algo_constants, log
from puya.avm import AVMType
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Intrinsic, UInt64Constant
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.optimize.dead_code_elimination import SIDE_EFFECT_FREE_AVM_OPS
from puya.ir.register_read_collector import RegisterReadCollector
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation
from puya.utils import biguint_bytes_eval, biguint_bytes_length, method_selector_hash, set_add

logger = log.get_logger(__name__)


_AnyOp = models.Op | models.ControlOp | models.Phi

_RegisterAssignments = Mapping[models.Register, models.Assignment]

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
_CONSTANT_TOO_BIG_TO_EXPAND = {
    AVMOp.itob.code,
    AVMOp.bzero.code,
}
_CONSTANT_EVALUABLE: typing.Final[frozenset[str]] = (
    COMPILE_TIME_CONSTANT_OPS - _CONSTANT_TOO_BIG_TO_EXPAND
)


def intrinsic_simplifier(context: IROptimizationContext, subroutine: models.Subroutine) -> bool:
    if context.expand_all_bytes:
        work_list = _AssignmentWorkQueue(COMPILE_TIME_CONSTANT_OPS)
    else:
        work_list = _AssignmentWorkQueue(_CONSTANT_EVALUABLE)
    ssa_reads = _SSAReadTracker()

    register_assignments = dict[models.Register, models.Assignment]()
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
        simplified = _try_fold_intrinsic(register_assignments, source)
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
            if (
                isinstance(op, models.Assignment)
                and isinstance(op.source, models.Intrinsic)
                and op.source.args
            ):
                with_immediates = _try_convert_stack_args_to_immediates(op.source)
                if with_immediates is not None:
                    logger.debug(f"Simplified {op.source} to {with_immediates}")
                    op.source = with_immediates
                    modified += 1

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
        self._set = set[Sequence[models.Register]]()

    def enqueue(self, op: models.Assignment) -> bool:
        if (
            isinstance(op.source, models.Intrinsic)
            and op.source.op.code in self._constant_evaluable
            and set_add(self._set, op.targets)
        ):
            self._dq.append((op, op.source))
            return True
        return False

    def dequeue(self) -> tuple[models.Assignment, models.Intrinsic]:
        op, source = self._dq.popleft()
        assert source is op.source
        self._set.remove(op.targets)
        return op, source

    def __bool__(self) -> int:
        return bool(self._dq)


class _SSAReadTracker:
    def __init__(self) -> None:
        self._data = defaultdict[models.Register, set[_AnyOp]](set)

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
    def visit_assignment(self, ass: models.Assignment) -> models.Assignment:
        # don't visit target(s), needs to stay as Register
        ass.source = ass.source.accept(self)
        return ass

    @typing.override
    def visit_phi(self, phi: models.Phi) -> models.Phi:
        # don't visit phi nodes, needs to stay as Register
        return phi

    @typing.override
    def visit_register(self, reg: models.Register) -> models.Value:  # type: ignore[override]
        if reg != self.register:
            return reg
        self.modified += 1
        return self.replacement


def _simplify_conditional_branches(
    subroutine: models.Subroutine, register_intrinsics: Mapping[models.Register, models.Intrinsic]
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
    subroutine: models.Subroutine, register_intrinsics: Mapping[models.Register, models.Intrinsic]
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
    intrinsic: Intrinsic, register_intrinsics: Mapping[models.Register, models.Intrinsic]
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
        elif cond in register_intrinsics:
            cond_op = register_intrinsics[cond]  # type: ignore[index]
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
    if cond in register_assignments:
        cond_defn = register_assignments[cond]  # type: ignore[index]
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
                intrinsic, a, b, bool_context=True
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
    register_assignments: _RegisterAssignments, intrinsic: models.Intrinsic
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
            case [a, b, c]:
                bool_arg_maybe_simplified = _try_simplify_bool_condition(register_assignments, c)
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
                    byte_arg in register_assignments
                    # don't do this optimisation for extract3 when the final argument is a constant
                    # zero, because of behaviour differences
                    and (intrinsic.immediates or L > 0)
                ):
                    match register_assignments[byte_arg].source:  # type: ignore[index]
                        case models.Intrinsic(
                            op=AVMOp.extract, args=[src_bytes_arg], immediates=[int(src_start), 0]
                        ):
                            # simplify a chained extract
                            return models.Intrinsic(
                                op=AVMOp.extract,
                                args=[src_bytes_arg],
                                immediates=[S + src_start, L],
                                source_location=op_loc,
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
            ) if (byte_const := _get_byte_constant(register_assignments, byte_arg)) is not None:
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
                return _try_simplify_bytes_unary_op(register_assignments, intrinsic, x)
            case [
                models.Value(atype=AVMType.bytes) as a,
                models.Value(atype=AVMType.bytes) as b,
            ]:
                return _try_simplify_bytes_binary_op(register_assignments, intrinsic, a, b)

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


def _decode_address(address: str) -> bytes:
    # Pad address so it's a valid b32 string
    padded_address = address + (6 * "=")
    address_bytes = base64.b32decode(padded_address)
    public_key_hash = address_bytes[: algo_constants.PUBLIC_KEY_HASH_LENGTH]
    return public_key_hash


def _get_byte_constant(
    register_assignments: _RegisterAssignments, byte_arg: models.Value
) -> models.BytesConstant | None:
    if byte_arg in register_assignments:
        byte_arg_defn = register_assignments[byte_arg]  # type: ignore[index]
        match byte_arg_defn.source:
            case models.Intrinsic(op=AVMOp.itob, args=[models.UInt64Constant(value=itob_arg)]):
                return _eval_itob(itob_arg, byte_arg_defn.source_location)
            case models.Intrinsic(op=AVMOp.bzero, args=[models.UInt64Constant(value=bzero_arg)]):
                return _eval_bzero(bzero_arg, byte_arg_defn.source_location)
            case models.Intrinsic(op=AVMOp.sha256, args=[models.BytesConstant(value=sha256_arg)]):
                return _eval_sha256(sha256_arg, byte_arg_defn.source_location)
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                return models.BytesConstant(
                    value=_decode_address(algo_constants.ZERO_ADDRESS),
                    encoding=AVMBytesEncoding.base32,
                    source_location=byte_arg.source_location,
                )
    elif isinstance(byte_arg, models.Constant):
        if isinstance(byte_arg, models.BytesConstant):
            return byte_arg
        if isinstance(byte_arg, models.BigUIntConstant):
            return _biguint_constant_to_bytes_constant(byte_arg)
        if isinstance(byte_arg, models.AddressConstant):
            return models.BytesConstant(
                value=_decode_address(byte_arg.value),
                encoding=AVMBytesEncoding.base32,
                source_location=byte_arg.source_location,
            )
        if isinstance(byte_arg, models.MethodConstant):
            return models.BytesConstant(
                value=method_selector_hash(byte_arg.value),
                encoding=AVMBytesEncoding.base16,
                source_location=byte_arg.source_location,
            )
    return None


def _get_bytes_length_safe(
    register_assignments: _RegisterAssignments, byte_arg: models.Value
) -> int | None:
    assert byte_arg.atype is AVMType.bytes
    if byte_arg in register_assignments:
        byte_arg_defn = register_assignments[byte_arg]  # type: ignore[index]
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


def _try_simplify_uint64_unary_op(
    intrinsic: models.Intrinsic, arg: models.Value
) -> models.Value | None:
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
        elif intrinsic.op is AVMOp.bitlen:
            return UInt64Constant(value=x.bit_length(), source_location=op_loc)
        elif intrinsic.op is AVMOp.itob:
            return _eval_itob(x, op_loc)
        elif intrinsic.op is AVMOp.bzero:
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
            elif intrinsic.op is AVMOp.len_:
                length = len(byte_const.value)
                return models.UInt64Constant(value=length, source_location=op_loc)
            elif intrinsic.op is AVMOp.bitlen:
                converted = int.from_bytes(byte_const.value, byteorder="big", signed=False)
                return UInt64Constant(value=converted.bit_length(), source_location=op_loc)
            else:
                logger.debug(f"Don't know how to simplify {intrinsic.op.code} of {byte_const}")
        elif arg in register_assignments and intrinsic.op is AVMOp.btoi:
            # extract* BYTES, START, LEN; btoi -> extract_uint* BYTES, START
            match register_assignments[arg].source:  # type: ignore[index]
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
    intrinsic: models.Intrinsic, a: models.Value, b: models.Value, *, bool_context: bool = False
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
    if not isinstance(c, int):
        return c
    if c < 0:
        # Value cannot be folded as it would result in a negative uint64
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
