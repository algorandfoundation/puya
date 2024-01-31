import itertools
import typing
from collections.abc import Iterable, Sequence

import attrs
import structlog

from puya.codegen import ops, teal
from puya.codegen.context import SubroutineCodeGenContext
from puya.codegen.stack import Stack
from puya.utils import invert_ordered_binary_op

logger = structlog.get_logger(__name__)

# Note: implementation of the koopmans algorithm part of http://www.euroforth.org/ef06/shannon-bailey06.pdf
# see also https://users.ece.cmu.edu/~koopman/stack_compiler/stack_co.html#appendix


@attrs.define
class UsagePair:
    a: ops.LoadVirtual | ops.StoreVirtual
    b: ops.LoadVirtual
    a_index: int
    b_index: int

    @staticmethod
    def by_distance(pair: "UsagePair") -> tuple[int, int, int]:
        return pair.b_index - pair.a_index, pair.a_index, pair.b_index


def find_usage_pairs(block: ops.MemoryBasicBlock) -> list[UsagePair]:
    # find usage pairs of variables within the block
    # the first element of the pair is an op that defines or uses a variable
    # the second element of the pair is an op that uses the variable
    # return pairs in ascending order, based on the number of instruction between each pair
    variables = dict[str, list[tuple[int, ops.StoreVirtual | ops.LoadVirtual]]]()
    for index, op in enumerate(block.ops):
        match op:
            case ops.StoreVirtual(local_id=local_id) | ops.LoadVirtual(local_id=local_id):
                variables.setdefault(local_id, []).append((index, op))

    pairs = list[UsagePair]()
    for uses in variables.values():
        for (a_index, a), (b_index, b) in itertools.pairwise(uses):
            if isinstance(b, ops.StoreVirtual):
                continue  # skip redefines, if they are used they will be picked up in next pair
            pairs.append(UsagePair(a=a, b=b, a_index=a_index, b_index=b_index))

    return sorted(pairs, key=UsagePair.by_distance)


def _get_stack_after_op(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock, target_op: ops.BaseOp | int
) -> Stack:
    stack = Stack.for_full_stack(subroutine, block)
    if isinstance(target_op, int):
        if target_op == -1:
            return stack
        assert target_op >= 0

    for idx, op in enumerate(block.ops):
        op.accept(stack)
        if target_op in (op, idx):
            break

    return stack


def copy_usage_pairs(
    subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock, pairs: list[UsagePair]
) -> None:
    # 1. copy define or use to bottom of l-stack
    # 2. replace usage with instruction to rotate the value from the bottom of l-stack to the top

    # to copy: dup, cover {stack_height}
    # to rotate: uncover {stack_height} - 1

    replaced_ops = dict[ops.StoreOp | ops.LoadOp, ops.LoadOp]()
    for pair in pairs:
        local_id = pair.a.local_id
        # step 1. copy define or use to bottom of stack

        # note: pairs may refer to ops that have been replaced by an earlier iteration
        a = replaced_ops.get(pair.a, pair.a)
        # redetermine index as block ops may have changed
        a_index = block.ops.index(a)

        # insert replacement before store, or after load
        insert_index = a_index if isinstance(a, ops.StoreVirtual) else a_index + 1
        # determine stack height at point of insertion
        insert_stack_in = _get_stack_after_op(subroutine, block, insert_index - 1)

        dup = ops.StoreLStack(
            cover=len(insert_stack_in.l_stack) - 1,
            local_id=local_id,
            source_location=a.source_location,
            atype=a.atype,
        )
        block.ops.insert(insert_index, dup)
        logger.debug(f"Inserted {block.block_name}.ops[{insert_index}]: '{dup}'")

        # step 2. replace b usage with instruction to rotate the value from the bottom of the stack
        b = replaced_ops.get(pair.b, pair.b)
        b_index = block.ops.index(b)

        uncover = ops.LoadLStack(
            local_id=local_id,
            source_location=b.source_location,
            atype=b.atype,
        )
        # replace op
        block.ops[b_index] = uncover

        # remember replacement in case it is part of another pair
        replaced_ops[b] = uncover
        logger.debug(f"Replaced {block.block_name}.ops[{b_index}]: '{b}' with '{uncover}'")


def is_stack_swap(stack_before_op: Stack, op: ops.MemoryOp) -> bool:
    teal_ops = op.accept(stack_before_op.copy())
    match teal_ops:
        case [teal.Cover(1) | teal.Uncover(1)]:
            return True
    return False


def optimize_single(stack_before_a: Stack, a: ops.BaseOp) -> ops.BaseOp | None:
    if isinstance(a, ops.MemoryOp):
        teal_ops = a.accept(stack_before_a.copy())
        match teal_ops:
            case [teal.Cover(0) | teal.Uncover(0)]:
                return ops.VirtualStackOp(a)
    return a


def is_redundant_rotate(
    stack_before_a: Stack, a: ops.MemoryOp, maybe_virtual: ops.BaseOp | None, b: ops.MemoryOp
) -> bool:
    stack = stack_before_a.copy()
    a_teal = a.accept(stack)
    try:
        (a_op,) = a_teal
    except ValueError:
        return False

    # optimization: the virtual op is applied here instead of outside optimize_pair
    # as it is a hot path so deferring it until it is actually required saves some time

    if maybe_virtual:
        maybe_virtual.accept(stack)
    b_teal = b.accept(stack)
    try:
        (b_op,) = b_teal
    except ValueError:
        return False
    match a_op, b_op:
        case teal.Cover(n=a_n), teal.Uncover(n=b_n) if a_n == b_n:
            return True
        case teal.Uncover(n=a_n), teal.Cover(n=b_n) if a_n == b_n:
            return True
        case teal.Cover(n=1), teal.Cover(n=1):
            return True
        case teal.Uncover(n=1), teal.Uncover(n=1):
            return True
    return False


COMMUTATIVE_OPS = frozenset(
    [
        "+",
        "*",
        "&",
        "&&",
        "|",
        "||",
        "^",
        "==",
        "!=",
        "b*",
        "b+",
        "b&",
        "b|",
        "b^",
        "b==",
        "b!=",
        "addw",
        "mulw",
    ]
)
ORDERING_OPS = frozenset(["<", "<=", ">", ">=", "b<", "b<=", "b>", "b>="])


def optimize_pair(
    ctx: SubroutineCodeGenContext,
    stack: Stack,  # stack state before a
    a: ops.BaseOp,
    maybe_virtual: ops.BaseOp | None,  # represents virtual ops that may be between a and b
    b: ops.BaseOp,
) -> tuple[()] | tuple[ops.BaseOp] | tuple[ops.BaseOp, ops.BaseOp]:
    """Given a pair of ops, returns which ops should be kept including replacements"""

    # this function has been optimized to reduce the number of isinstance checks,
    # consider this when making any modifications

    if isinstance(b, ops.StoreVirtual) and b.local_id not in ctx.vla.get_live_out_variables(b):
        # aka dead store removal
        match a:
            case ops.StoreLStack(copy=True) | ops.StoreXStack(copy=True) as cover:
                # this should handle both x-stack and l-stack cases StoreLStack is used to:
                #   1.) store a variable for retrieval later via a load
                #   2.) store a copy at the bottom of the stack for use in a later op
                # If it is a dead store, then the 1st scenario is no longer needed
                # and instead just need to ensure the value is moved to the bottom of the stack
                return (attrs.evolve(cover, copy=False),)
        return a, ops.Pop(n=1, source_location=b.source_location)

    # optimization: cases after here are only applicable if "a" is a MemoryOp
    if not isinstance(a, ops.MemoryOp):
        return a, b

    if isinstance(b, ops.Pop) and b.n == 1 and isinstance(a, ops.LoadOp):
        return ops.VirtualStackOp(a), ops.VirtualStackOp(b)

    if isinstance(b, ops.IntrinsicOp) and is_stack_swap(stack, a):
        if b.op_code in COMMUTATIVE_OPS:
            if isinstance(a, ops.LoadLStack | ops.StoreLStack):
                return (b,)
            return ops.VirtualStackOp(a), b
        elif b.op_code in ORDERING_OPS:
            inverse_ordering_op = invert_ordered_binary_op(b.op_code)
            new_b = attrs.evolve(b, op_code=inverse_ordering_op)
            if isinstance(a, ops.LoadLStack | ops.StoreLStack):
                return (new_b,)
            return ops.VirtualStackOp(a), new_b

    # optimization: cases after here are only applicable if "b" is a MemoryOp
    if not isinstance(b, ops.MemoryOp):
        return a, b

    if is_redundant_rotate(stack, a, maybe_virtual, b):
        match a, b:
            case (
                ops.LoadLStack(copy=False, local_id=a_local_id),
                ops.StoreLStack(copy=False, local_id=b_local_id),
            ) if a_local_id == b_local_id:
                # loading and storing to the same spot in the same stack can be removed entirely
                # if the local_id does not change
                return ()
        # otherwise keep around as virtual stack op
        return ops.VirtualStackOp(a), ops.VirtualStackOp(b)

    if isinstance(a, ops.LoadOp) and isinstance(b, ops.StoreOp):
        if a.local_id == b.local_id:
            match a, b:
                case ops.LoadLStack(copy=False) as load, ops.StoreLStack(copy=True):
                    return (attrs.evolve(load, copy=True),)
                case ops.LoadXStack(), ops.StoreXStack(copy=False):
                    return ()
                case ops.LoadFStack(), ops.StoreFStack():
                    return ()
                case ops.LoadVirtual(), ops.StoreVirtual():
                    return ()
    else:
        match a, b:
            case (
                ops.StoreParam(copy=False, local_id=a_local_id) as store_param,
                ops.LoadParam(local_id=b_local_id),
            ) if a_local_id == b_local_id:
                # if we have a store to param and then read from param,
                # we can reduce the program size byte 1 byte by copying
                # and then storing instead
                # i.e. frame_bury -x; frame_dig -x
                # =>   dup; frame_bury -x
                store_with_copy = attrs.evolve(store_param, copy=True)
                return (store_with_copy,)
    return a, b


_T = typing.TypeVar("_T")


class _Unset:
    pass


_unset = _Unset()


class ManualIter(typing.Generic[_T]):
    def __init__(self, items: Iterable[_T]) -> None:
        self._iter = iter(items)
        self._next: _T | _Unset | None = _unset

    def next(self) -> _T | None:
        result = self.peek() if self._next is _unset else self._next
        assert not isinstance(result, _Unset)
        self._next = _unset
        return result

    def peek(self) -> _T | None:
        if self._next is _unset:
            self._next = next(self._iter, None)
        assert not isinstance(self._next, _Unset)
        return self._next


def _merge_virtual_ops(maybe_virtuals: Sequence[ops.BaseOp]) -> Sequence[ops.BaseOp]:
    result = list[ops.BaseOp]()
    virtuals = list[ops.VirtualStackOp]()
    # final None will trigger merging any remaining virtuals
    for op in [*maybe_virtuals, None]:
        # note: uses type instead of isinstance because this is a
        # hotspot as determined by profiling. VirtualStackOp
        # has been annotated with @typing.final so that this is equivalent here
        if type(op) is ops.VirtualStackOp:  # collect virtual ops
            virtuals.append(op)
            continue
        if virtuals:  # merge any existing virtuals if non-virtual found
            if len(virtuals) > 1:
                virtual_op = ops.VirtualStackOp(
                    original=[o for v in virtuals for o in v.original],
                    replacement=[r for v in virtuals for r in v.replacement or ()],
                )
            else:
                virtual_op = virtuals[0]
            result.append(virtual_op)
            virtuals = []
        if op:
            result.append(op)
    return result


def peephole_optimization(ctx: SubroutineCodeGenContext) -> None:
    # replace sequences of stack manipulations with shorter ones
    vla_modified = False
    for block in ctx.subroutine.body:
        while (result := peephole_optimization_single(ctx, block)) and result.modified:
            vla_modified = vla_modified or result.vla_modified
        vla_modified = vla_modified or result.vla_modified
    if vla_modified:
        ctx.invalidate_vla()


@attrs.define(kw_only=True)
class PeepholeResult:
    modified: bool
    vla_modified: bool


def peephole_optimization_single(
    ctx: SubroutineCodeGenContext, block: ops.MemoryBasicBlock
) -> PeepholeResult:
    result = list[ops.BaseOp]()
    op_iter = ManualIter(block.ops)
    b = op_iter.next()
    stack = Stack.for_full_stack(ctx.subroutine, block)
    vla_modified = False
    while b:
        a = b
        b = op_iter.next()

        # sequential virtual ops get merged, however there could still be a virtual
        # op between two non-virtual ops
        # so see if this is the case, and if so do peephole optimization across the two
        # non-virtual ops to allow potential further optimizations
        maybe_virtual: ops.VirtualStackOp | None = None
        match a, b:
            case ops.VirtualStackOp(), _:
                pass
            case _, ops.VirtualStackOp(replacement=None) as virtual_b:
                c = op_iter.peek()
                if not isinstance(c, ops.VirtualStackOp):
                    maybe_virtual = virtual_b
                    b = op_iter.next()
        #
        if b:
            ops_to_keep: Sequence[ops.BaseOp] = optimize_pair(ctx, stack, a, maybe_virtual, b)
        else:
            ops_to_keep = (a,)
        if (
            not vla_modified
            and (a not in ops_to_keep and isinstance(a, ops.StoreVirtual | ops.LoadVirtual))
            or (b not in ops_to_keep and isinstance(b, ops.StoreVirtual | ops.LoadVirtual))
        ):
            vla_modified = True
        # based on peephole optimization result, insert virtual op
        if maybe_virtual is not None:
            if len(ops_to_keep) == 2:
                ops_to_keep = ops_to_keep[0], maybe_virtual, ops_to_keep[1]
            else:
                ops_to_keep = (*ops_to_keep, maybe_virtual)

        # merge sequential virtual ops
        ops_to_keep = _merge_virtual_ops(ops_to_keep)

        # finally, insert resulting ops
        for op in ops_to_keep:
            if op is b:
                # don't add b yet, it might be optimized away in a later iteration
                continue
            maybe_op = optimize_single(stack, op)
            if maybe_op:
                maybe_op.accept(stack)
                result.append(maybe_op)
        if b not in ops_to_keep:
            # skip to next b
            b = op_iter.next()

    before = block.ops
    block.ops = result
    return PeepholeResult(modified=before != result, vla_modified=vla_modified)


def koopmans(ctx: SubroutineCodeGenContext) -> None:
    for block in ctx.subroutine.body:
        usage_pairs = find_usage_pairs(block)
        copy_usage_pairs(ctx.subroutine, block, usage_pairs)
    peephole_optimization(ctx)
