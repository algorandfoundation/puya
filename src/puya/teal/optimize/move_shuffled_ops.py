import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.parse import sequential_source_locations_merge
from puya.teal import models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize._data import LOAD_OP_CODES
from puya.teal.optimize.peephole import is_stack_swap

logger = log.get_logger(__name__)


_INTC_OPS: typing.Final = frozenset(
    {
        "intc",
        *(f"intc_{i}" for i in range(4)),
    }
)
_BYTEC_OPS: typing.Final = frozenset(
    {
        "bytec",
        *(f"bytec_{i}" for i in range(4)),
    }
)
_ITXN_RESULT_OPS: typing.Final = frozenset(
    {
        "itxn",
        "itxna",
        "gitxn",
        "gitxna",
    }
)
_MOVABLE_OPS: typing.Final = frozenset(
    {
        *LOAD_OP_CODES,
        "frame_dig",
    }
)
# these ops are all pure and take 1 stack input and produce 1 stack output
_PURE_TRANSFORM_OPS: typing.Final = frozenset(
    {
        # arithmetic / byte-array
        "itob",
        "btoi",
        "len",
        "bitlen",
        "sqrt",
        "bsqrt",
        "bzero",
        "!",
        "~",
        "b~",
        # hash & cryptographic functions
        "sha256",
        "sha512_256",
        "sha3_256",
        "keccak256",
        "mimc",
        "sumhash512",
        "ec_map_to",
        "ec_subgroup_check",
        # byte manipulation
        "extract",
        "substring",
        "base64_decode",
        # transaction level constants
        "block",
        "args",
        "txnas",
        "gtxns",
        "gtxnsa",
        "gtxnas",
        "gaids",
        "gloads",
    }
)


def move_shuffled_ops(block: models.TealBlock) -> bool:
    """
    Remove rotation ops by moving op sequences.

    Drop cover: `<expr ΔN>; <producer_chain>; cover N` -> `<producer_chain>; <expr ΔN>`
    Drop uncover: `<producer_chain>; <expr ΔN>; uncover N` -> `<expr ΔN>; <producer_chain>`
    <expr ΔN> is a series of ops with a stack delta of N
    <producer_chain> is a MOVABLE_OP followed by zero or more PURE_TRANSFORM_OPS
    """
    ops = block.ops
    modified = False
    idx = 0
    while idx < len(ops):
        plan = _plan_drop_cover(ops, idx)
        if plan is None:
            plan = _plan_drop_uncover(ops, idx)
        if plan is None:
            idx += 1
        else:
            preserve_stack_manipulations(ops, plan.window, plan.new_ops)
            idx = plan.next_idx
            modified = True
    return modified


@attrs.frozen
class _Plan:
    window: slice
    new_ops: Sequence[models.TealOp]
    next_idx: int


def _plan_drop_cover(ops: Sequence[models.TealOp], idx: int) -> _Plan | None:
    #         ops: ..., *expr_ops, ..., adjacent_op, producer, *transforms, op_to_drop, ...
    #     indexes:      ^expr_idx                    ^producer_idx          ^idx

    op_to_drop = ops[idx]
    rotation_depth = _get_rotate_depth(op_to_drop, rotation_op_type=models.Cover)
    if rotation_depth is None:
        return None
    producer_idx = _find_previous_movable_op(ops, end_idx=idx)
    if producer_idx is None:
        return None
    expr_idx = _find_previous_index_with_stack_depth(
        ops, end_idx=producer_idx, target_depth=rotation_depth
    )
    if expr_idx is None:
        return None
    adjacent_op = ops[producer_idx - 1]
    producer = ops[producer_idx]
    producer_ops = ops[producer_idx:idx]
    expr_ops = ops[expr_idx:producer_idx]
    if len(producer_ops) > 1 and _is_same_op(adjacent_op, producer):
        _log_skip(
            ops_to_move=producer_ops,
            op_to_drop=op_to_drop,
            reason=f"would separate dupable ops `{adjacent_op.teal()}`",
        )
        return None
    if not _can_move_through_ops(expr_ops, producer):
        _log_skip(
            ops_to_move=producer_ops,
            op_to_drop=op_to_drop,
            reason=f"cannot safely move through {len(expr_ops)} ops",
        )
        return None
    _log_move(producer_ops, from_idx=producer_idx, to_idx=expr_idx, dropped=op_to_drop)
    return _Plan(
        window=slice(expr_idx, idx + 1),
        new_ops=[*producer_ops, *ops[expr_idx:producer_idx]],
        next_idx=expr_idx + 1,
    )


def _plan_drop_uncover(ops: Sequence[models.TealOp], idx: int) -> _Plan | None:
    #     ops: ..., producer, *transform_ops, adjacent_op, *expr_ops, op_to_drop, ...
    # indexes:      ^producer_idx             ^expr_idx               ^idx
    op_to_drop = ops[idx]
    rotation_depth = _get_rotate_depth(op_to_drop, rotation_op_type=models.Uncover)
    if rotation_depth is None:
        return None
    expr_idx = _find_previous_index_with_stack_depth(ops, end_idx=idx, target_depth=rotation_depth)
    if expr_idx is None:
        return None
    producer_idx = _find_previous_movable_op(ops, end_idx=expr_idx)
    if producer_idx is None:
        return None
    producer = ops[producer_idx]
    producer_ops = ops[producer_idx:expr_idx]
    expr_ops = ops[expr_idx:idx]
    adjacent_op = ops[expr_idx]
    if len(producer_ops) == 1 and _is_same_op(producer, adjacent_op):
        _log_skip(
            ops_to_move=producer_ops,
            op_to_drop=op_to_drop,
            reason=f"would separate dupable ops `{adjacent_op.teal()}`",
        )
        return None
    if not _can_move_through_ops(expr_ops, producer):
        _log_skip(
            ops_to_move=producer_ops,
            op_to_drop=op_to_drop,
            reason=f"cannot safely move through {len(expr_ops)} ops",
        )
        return None
    dest_idx = idx - len(producer_ops)
    _log_move(producer_ops, from_idx=producer_idx, to_idx=dest_idx, dropped=op_to_drop)
    return _Plan(
        window=slice(producer_idx, idx + 1),
        new_ops=[*ops[expr_idx:idx], *producer_ops],
        next_idx=producer_idx + 1,
    )


def _get_rotate_depth[T: (models.Cover, models.Uncover)](
    op: models.TealOp, *, rotation_op_type: type[T]
) -> int | None:
    if is_stack_swap(op):
        return 1
    if isinstance(op, rotation_op_type) and op.n:
        return op.n
    return None


def _is_same_op(a: models.TealOp, b: models.TealOp) -> bool:
    return (a.op_code, a.immediates) == (b.op_code, b.immediates)


def _find_previous_movable_op(ops: Sequence[models.TealOp], *, end_idx: int) -> int | None:
    for idx in reversed(range(end_idx)):
        op_code = ops[idx].op_code
        if op_code in _PURE_TRANSFORM_OPS:
            continue
        if op_code in _MOVABLE_OPS:
            return idx
        break
    return None


def _find_previous_index_with_stack_depth(
    ops: Sequence[models.TealOp], *, end_idx: int, target_depth: int
) -> int | None:
    stack_depth = 0
    for op_idx in reversed(range(end_idx)):
        op = ops[op_idx]
        # cannot move past these ops
        if isinstance(op, models.ControlOp | models.Proto):
            return None
        stack_depth += op.stack_height_delta
        if stack_depth == target_depth:
            return op_idx
    return None


def _can_move_through_ops(ops: Sequence[models.TealOp], op_to_move: models.TealOp) -> bool:
    """Returns true if it is safe for op_to_move to move through (before or after) ops"""
    # used to track the stack depth does not drop below the current height
    relative_stack_depth = 0
    for op in ops:
        # op would consume the op_to_move value
        if op.consumes > relative_stack_depth:
            return False
        # op invalidates the value op_to_move would read
        if _is_barrier(op_to_move=op_to_move, maybe_barrier_op=op):
            return False
        relative_stack_depth += op.stack_height_delta
    return True


def _is_barrier(*, op_to_move: models.TealOp, maybe_barrier_op: models.TealOp) -> bool:
    """Returns true if maybe_barrier_op invalidates the value op_to_move would read."""
    moving_op_code = op_to_move.op_code
    if moving_op_code == "frame_dig":
        return (
            maybe_barrier_op.op_code == "frame_bury"
            and maybe_barrier_op.immediates == op_to_move.immediates
        )
    if moving_op_code == "load":
        return maybe_barrier_op.op_code == "stores" or (
            maybe_barrier_op.op_code == "store"
            and maybe_barrier_op.immediates == op_to_move.immediates
        )
    if moving_op_code in _ITXN_RESULT_OPS:
        return maybe_barrier_op.op_code == "itxn_submit"

    # defensive code: there should not be any constant blocks in the program at this point
    if moving_op_code in _INTC_OPS:
        return maybe_barrier_op.op_code == "intcblock"  # pragma: no cover
    if moving_op_code in _BYTEC_OPS:
        return maybe_barrier_op.op_code == "bytecblock"  # pragma: no cover
    return False


def _log_move(
    chain: Sequence[models.TealOp], *, from_idx: int, to_idx: int, dropped: models.TealOp
) -> None:
    teal = "; ".join(o.teal() for o in chain)
    logger.debug(
        f"moved `{teal}` from index {from_idx} to {to_idx}, dropped `{dropped.teal()}`",
        location=sequential_source_locations_merge(op.source_location for op in chain),
    )


def _log_skip(
    *,
    ops_to_move: Sequence[models.TealOp],
    op_to_drop: models.TealOp,
    reason: str,
) -> None:
    teal = "; ".join(o.teal() for o in ops_to_move)
    logger.debug(
        f"skipped moving `{teal}` to drop `{op_to_drop.teal()}`: {reason}",
        location=sequential_source_locations_merge(op.source_location for op in ops_to_move),
    )
