import functools
import itertools
import math
import typing
from collections.abc import Callable
from typing import Sequence

import attrs
import structlog

from puya.codegen import ops, teal
from puya.codegen.context import ProgramCodeGenContext
from puya.codegen.stack import Stack
from puya.codegen.stack_koopmans import peephole_optimization_single
from puya.codegen.vla import VariableLifetimeAnalysis
from puya.errors import InternalError

logger = structlog.get_logger(__name__)

SimplifyFunction: typing.TypeAlias = Callable[
    [tuple[teal.TealOp, ...]], Sequence[teal.TealOp] | None
]
TealOpSequence = tuple[teal.TealOp, ...]


@attrs.define
class MIRTealOps:
    mir_op: ops.BaseOp
    teal_ops: list[teal.TealOp]


def get_teal_ops(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock
) -> list[MIRTealOps]:
    stack = Stack.for_full_stack(subroutine, block)
    mir_teal_ops = []
    for block_op in block.ops:
        op_teal_ops = block_op.accept(stack)
        mir_teal_ops.append(MIRTealOps(block_op, op_teal_ops))
    return mir_teal_ops


def simplify_repeated_rotation_ops(
    maybe_simplify: Sequence[teal.TealOp],
) -> Sequence[teal.TealOp] | None:
    assert maybe_simplify
    first = maybe_simplify[0]
    assert isinstance(first, teal.Cover | teal.Uncover)
    is_cover = isinstance(first, teal.Cover)
    for other in maybe_simplify:
        if is_cover:
            assert isinstance(other, teal.Cover)
        else:
            assert isinstance(other, teal.Uncover)
        assert other.n == first.n

    n = first.n
    number_of_ops = len(maybe_simplify)
    number_of_inverse = n + 1 - number_of_ops
    while number_of_inverse < 0:
        number_of_inverse += n + 1
    if number_of_inverse >= number_of_ops:
        return None
    inverse_op = teal.Uncover(n=n) if is_cover else teal.Cover(n=n)
    return [inverse_op] * number_of_inverse


def get_possible_rotation_ops(n: int) -> list[teal.TealOp]:
    possible_ops = list[teal.TealOp]()
    for i in range(1, n + 1):
        possible_ops.append(teal.Cover(i))
        possible_ops.append(teal.Uncover(i))
    return possible_ops


class InvalidOpSequenceError(Exception):
    pass


class TealStack:
    stack: list[str] = attrs.field(factory=list)
    frame_vars: dict[int, str] = attrs.field(factory=dict)

    def __init__(self, stack_or_size: int | list[str], frame_vars: dict[int, str] | None = None):
        # build a list of unique numbers up to stack size
        # using strings as they are a little more readable
        self.stack = (
            stack_or_size
            if isinstance(stack_or_size, list)
            else [f"stack_{i}" for i in range(stack_or_size)]
        )
        self.frame_vars = {} if frame_vars is None else frame_vars

    def _check_index(self, index: int) -> None:
        if index < 0 or index >= len(self.stack):
            raise InvalidOpSequenceError

    def cover(self, n: int) -> None:
        if n == 0:
            return
        index = len(self.stack) - n - 1
        self._check_index(index)
        self.stack.insert(index, self.stack.pop())

    def uncover(self, n: int) -> None:
        if n == 0:
            return
        index = len(self.stack) - n - 1
        self._check_index(index)
        self.stack.append(self.stack.pop(index))

    def frame_dig(self, n: int) -> None:
        var = self.frame_vars.get(n, f"frame_dig_{n}")
        self.stack.append(var)

    def frame_bury(self, n: int) -> None:
        if not self.stack:
            raise InvalidOpSequenceError
        var = self.stack.pop()
        self.frame_vars[n] = var

    def dig(self, n: int) -> None:
        index = len(self.stack) - 1 - n
        self._check_index(index)
        var = self.stack[index]
        self.stack.append(var)

    def bury(self, n: int) -> None:
        if not self.stack:
            raise InvalidOpSequenceError
        index = len(self.stack) - 1 - n
        self._check_index(index)
        var = self.stack.pop()
        self.stack[index] = var

    def dup(self) -> None:
        if not self.stack:
            raise InvalidOpSequenceError
        var = self.stack[-1]
        self.stack.append(var)

    def apply(self, ops: Sequence[teal.TealOp]) -> None:
        for op in ops:
            match op:
                case teal.Cover(n=n):
                    self.cover(n)
                case teal.Uncover(n=n):
                    self.uncover(n)
                case teal.FrameDig(n=n):
                    self.frame_dig(n)
                case teal.FrameBury(n=n):
                    self.frame_bury(n)
                case teal.Dig(n=n):
                    self.dig(n)
                case teal.Bury(n=n):
                    self.bury(n)
                case teal.Dup():
                    self.dup()
                case teal.RetSub():
                    pass
                case _:
                    raise InvalidOpSequenceError

    def clone(self) -> "TealStack":
        return TealStack(self.stack.copy(), self.frame_vars.copy())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TealStack):
            return False
        return self.stack == other.stack and self.frame_vars == other.frame_vars


def map_from_frame_ops(
    teal_ops: Sequence[teal.TealOp], stack: TealStack
) -> tuple[teal.TealOp, ...]:
    result = list[teal.TealOp]()
    stack = stack.clone()
    for op in teal_ops:
        if isinstance(op, teal.FrameDig) and op.n >= 0:
            dig = teal.Dig(len(stack.stack) - op.n - 1)
            result.append(dig)
        elif isinstance(op, teal.FrameBury) and op.n >= 0:
            bury = teal.Bury(len(stack.stack) - op.n - 1)
            result.append(bury)
        else:
            result.append(op)
        stack.apply((op,))
    return tuple(result)


def map_to_frame_ops(teal_ops: Sequence[teal.TealOp], stack: TealStack) -> tuple[teal.TealOp, ...]:
    result = list[teal.TealOp]()
    stack = stack.clone()
    for op in teal_ops:
        if isinstance(op, teal.Dig):
            dig = teal.FrameDig(len(stack.stack) - op.n - 1)
            if dig.n < 0:
                raise InternalError(f"{dig.n} too small. Stack={len(stack.stack)}, op={op.n}")
            result.append(dig)
        elif isinstance(op, teal.Bury):
            bury = teal.FrameBury(len(stack.stack) - op.n - 1)
            if bury.n < 0:
                raise InternalError(f"{bury.n} too small. Stack={len(stack.stack)}, op={op.n}")
            result.append(bury)
        else:
            result.append(op)
        stack.apply((op,))

    return tuple(result)


def are_equivalent(
    stack: TealStack, original_ops: Sequence[teal.TealOp], simpler_ops: Sequence[teal.TealOp]
) -> bool:
    a = stack.clone()
    a.apply(original_ops)
    b = stack.clone()
    b.apply(simpler_ops)
    return a == b


def simplify_pairwise_ops(original_ops: TealOpSequence) -> TealOpSequence | None:
    remaining_ops = list(original_ops)
    modified = False
    result = list[teal.TealOp]()
    while remaining_ops:
        match remaining_ops:
            case [teal.FrameDig(n=dig_n), teal.FrameBury(n=bury_n), *tail] if dig_n == bury_n:
                modified = True
            case [teal.Cover(n=cover_n), teal.Uncover(n=uncover_n), *tail] if cover_n == uncover_n:
                modified = True
            case [teal.Uncover(n=uncover_n), teal.Cover(n=cover_n), *tail] if cover_n == uncover_n:
                modified = True
            case [keep, *tail]:
                result.append(keep)
            case _:
                raise InternalError("Unexpected empty sequence")
        remaining_ops = tail

    if modified:
        return tuple(result)
    return None


@functools.cache
def simplify_rotation_ops(
    original_ops: TealOpSequence,
) -> TealOpSequence | None:
    rot_op_ns = [o.n for o in original_ops if isinstance(o, teal.Cover | teal.Uncover)]
    if not rot_op_ns:
        return None  # nothing to change
    bury_op_ns = [o.n for o in original_ops if isinstance(o, teal.Bury | teal.FrameBury)]
    dig_op_ns = [o.n for o in original_ops if isinstance(o, teal.Dig | teal.FrameDig)]

    required_stack_size = (
        max(itertools.chain(rot_op_ns, bury_op_ns, dig_op_ns)) + len(bury_op_ns) + 1
    )
    original_stack = TealStack(required_stack_size)
    expected = original_stack.clone()
    original_frame_ops = map_to_frame_ops(original_ops, original_stack.clone())

    expected.apply(original_frame_ops)
    # entire sequence can be removed!
    if expected == original_stack:
        return ()

    fixed_ops = tuple(
        o for o in original_frame_ops if isinstance(o, teal.FrameDig | teal.FrameBury | teal.Dup)
    )
    n = max(rot_op_ns)
    possible_rotation_ops = get_possible_rotation_ops(n)

    # TODO: use a non-bruteforce approach and/or capture common simplifications as data
    for num_rotation_ops in range(len(rot_op_ns)):
        num_possible_ops = num_rotation_ops + len(fixed_ops)
        for maybe_rotation_ops in itertools.permutations(possible_rotation_ops, num_rotation_ops):
            assert isinstance(maybe_rotation_ops, tuple)
            possible_ops = maybe_rotation_ops + fixed_ops
            for maybe_ops in itertools.permutations(possible_ops, num_possible_ops):
                assert isinstance(maybe_ops, tuple)
                stack = original_stack.clone()
                try:
                    stack.apply(maybe_ops)
                except InvalidOpSequenceError:
                    continue
                if expected == stack:
                    if any(op for op in original_ops if isinstance(op, teal.Dig | teal.Bury)):
                        maybe_ops = map_from_frame_ops(maybe_ops, original_stack.clone())
                    assert are_equivalent(original_stack.clone(), original_ops, maybe_ops)
                    return maybe_ops
    return None


def _teal_ops_str(teal_ops: Sequence[teal.TealOp]) -> str:
    return "; ".join(map(str, teal_ops))


def try_simplify(
    maybe_simplify: list[MIRTealOps],
    simplification_function: SimplifyFunction,
    block_ops: list[ops.BaseOp],
) -> bool:
    maybe_simplify_teal = tuple(
        itertools.chain.from_iterable(op.teal_ops for op in maybe_simplify)
    )
    simpler = simplification_function(maybe_simplify_teal)
    if simpler is None:
        return False
    first_op = maybe_simplify[0].mir_op
    last_op = maybe_simplify[-1].mir_op
    replace_slice = slice(block_ops.index(first_op), block_ops.index(last_op) + 1)
    to_replace = block_ops[replace_slice]
    flattened_virtual_ops = list[ops.MemoryOp]()
    for op in to_replace:
        match op:
            case ops.VirtualStackOp() as virtual:
                flattened_virtual_ops.extend(virtual.original)
            case ops.MemoryOp() as memory:
                flattened_virtual_ops.append(memory)
            case ops.RetSub() as retsub if simpler and isinstance(simpler[-1], teal.RetSub):
                flattened_virtual_ops.append(retsub)
            case _:
                # can't simplify... this shouldn't happen?
                logger.debug(
                    f"Couldn't replace {_teal_ops_str(maybe_simplify_teal)} ops with "
                    f"{_teal_ops_str(simpler)} ops because of {op}"
                )
                return False
    logger.debug(f"Simplified {_teal_ops_str(maybe_simplify_teal)} to {_teal_ops_str(simpler)}")
    block_ops[replace_slice] = [
        ops.VirtualStackOp(
            original=flattened_virtual_ops,
            replacement=simpler,
        )
    ]
    return True


def _is_valid_repeat_op(repeated: list[MIRTealOps], op: MIRTealOps) -> bool:
    if not repeated:
        # can't determine if valid from an empty sequence
        if not op.teal_ops:
            return False
        # no existing ops, so test teal ops against themselves
        last, *others = op.teal_ops
        if not isinstance(last, teal.Cover | teal.Uncover):
            return False
    else:
        # compare new op to existing sequence
        last = next(itertools.chain.from_iterable(r.teal_ops for r in repeated))
        others = op.teal_ops
    return all(last == op for op in others)


def try_simplify_repeated_ops(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock
) -> None:
    mir_teal_ops = get_teal_ops(subroutine, block)
    repeated = list[MIRTealOps]()
    for mir_teal_op in mir_teal_ops:
        if _is_valid_repeat_op(repeated, mir_teal_op):
            repeated.append(mir_teal_op)
        elif repeated:
            if len(repeated) > 1:
                try_simplify(repeated, simplify_repeated_rotation_ops, block.ops)
            repeated = []
            # op might still be valid as the start of a new sequence
            if _is_valid_repeat_op(repeated, mir_teal_op):
                repeated.append(mir_teal_op)
    if repeated:  # probably shouldn't happen due to control ops terminating the sequence earlier
        try_simplify(repeated, simplify_repeated_rotation_ops, block.ops)


def try_simplify_pairwise_ops(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock
) -> None:
    mir_teal_ops = get_teal_ops(subroutine, block)
    to_simplify = list[MIRTealOps]()
    for mir_teal_op in mir_teal_ops:
        to_simplify.append(mir_teal_op)
        if sum(len(o.teal_ops) for o in to_simplify) > 1:
            try_simplify(to_simplify, simplify_pairwise_ops, block.ops)
            to_simplify = []


MAX_PERMUTATIONS = 2000


def get_estimated_permutations(maybe_simplify: Sequence[MIRTealOps]) -> int:
    teal_ops = itertools.chain.from_iterable(o.teal_ops for o in maybe_simplify)
    rot_op_ns = [o.n for o in teal_ops if isinstance(o, teal.Cover | teal.Uncover)]
    if not rot_op_ns:
        return 0
    fixed_permutations = math.factorial(len(maybe_simplify) - len(rot_op_ns))
    max_n = max(rot_op_ns) + 1
    rotation_choices = max_n * 2
    total = 0
    for num_rot_ops in range(len(rot_op_ns)):
        total += rotation_choices**num_rot_ops * fixed_permutations
    return total


def _can_maybe_be_simplified(op: MIRTealOps) -> bool:
    return all(
        isinstance(
            teal_op,
            teal.Cover
            | teal.Uncover
            | teal.Bury
            | teal.Dig
            | teal.FrameBury
            | teal.FrameDig
            | teal.Dup,
        )
        for teal_op in op.teal_ops
    )


def try_simplify_rotation_ops(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock
) -> None:
    mir_teal_ops = get_teal_ops(subroutine, block)
    maybe_remove_rotations = list[MIRTealOps]()
    for mir_teal_op in mir_teal_ops:
        if _can_maybe_be_simplified(mir_teal_op):
            maybe_remove_rotations.append(mir_teal_op)
            if get_estimated_permutations(maybe_remove_rotations) >= MAX_PERMUTATIONS:
                modified = try_simplify(maybe_remove_rotations, simplify_rotation_ops, block.ops)
                if modified:
                    maybe_remove_rotations = []
                else:
                    maybe_remove_rotations.pop(0)
        elif maybe_remove_rotations:
            try_simplify(maybe_remove_rotations, simplify_rotation_ops, block.ops)
            maybe_remove_rotations = []


def simplify_teal_ops(context: ProgramCodeGenContext, subroutine: ops.MemorySubroutine) -> None:
    vla = VariableLifetimeAnalysis.analyze(subroutine)
    for block in subroutine.body:
        peephole_optimization_single(subroutine, vla, block)
        try_simplify_repeated_ops(subroutine, block)
        try_simplify_pairwise_ops(subroutine, block)
        if context.options.optimization_level >= 2:
            try_simplify_rotation_ops(subroutine, block)
