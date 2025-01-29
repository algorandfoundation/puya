import attrs

from puya.teal import models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize._data import (
    COMMUTATIVE_OPS,
    LOAD_OP_CODES,
    LOAD_OP_CODES_INCL_OFFSET,
    ORDERING_OPS,
    STORE_OPS_INCL_OFFSET,
)
from puya.utils import invert_ordered_binary_op


def peephole(block: models.TealBlock, opt_level: int) -> bool:
    start_idx = 0
    stack_height = block.entry_stack_height
    any_modified = False
    result = block.ops.copy()
    while start_idx < len(result):
        modified = False
        window: slice | None = None
        if opt_level > 0 and not modified and start_idx < len(result) - 3:
            window = slice(start_idx, start_idx + 4)
            new_values, modified = _optimize_quadruplet(*result[window])
        if opt_level > 0 and not modified and start_idx < len(result) - 2:
            window = slice(start_idx, start_idx + 3)
            new_values, modified = _optimize_triplet(*result[window], stack_height=stack_height)
        if not modified and start_idx < len(result) - 1:
            window = slice(start_idx, start_idx + 2)
            new_values, modified = _optimize_pair(*result[window])
        if not modified:
            window = slice(start_idx, start_idx + 1)
            new_values, modified = optimize_single(*result[window])
        if modified:
            assert window is not None
            any_modified = True
            preserve_stack_manipulations(result, window, new_values)
        else:
            stack_height += result[start_idx].stack_height_delta
            start_idx += 1  # go to next
    block.ops[:] = result
    return any_modified


def is_redundant_rotate(a: models.TealOp, b: models.TealOp) -> bool:
    match a, b:
        case models.Cover(n=a_n), models.Uncover(n=b_n) if a_n == b_n:
            return True
        case models.Uncover(n=a_n), models.Cover(n=b_n) if a_n == b_n:
            return True

    return is_stack_swap(a) and is_stack_swap(b)


def is_stack_swap(op: models.TealOp) -> bool:
    return op.op_code == "swap" or (op.op_code in ("cover", "uncover") and op.immediates[0] == 1)


def optimize_single(a: models.TealOp) -> tuple[list[models.TealOp], bool]:
    if a.op_code in ("cover", "uncover") and a.immediates == (0,):
        return [], True
    if a.op_code == "dig" and a.immediates == (0,):
        return [
            models.Dup(
                source_location=a.source_location,
                stack_manipulations=a.stack_manipulations,
            )
        ], True
    if a.op_code == "popn" and a.immediates == (1,):
        return [
            models.Pop(
                source_location=a.source_location,
                stack_manipulations=a.stack_manipulations,
            )
        ], True
    return [a], False


def _optimize_pair(a: models.TealOp, b: models.TealOp) -> tuple[list[models.TealOp], bool]:
    if is_redundant_rotate(a, b):
        return [], True

    if is_stack_swap(a):
        # `swap; pop` -> `bury 1`
        if b.op_code == "pop":
            return [models.Bury(n=1, source_location=b.source_location)], True
        if b.op_code in COMMUTATIVE_OPS:
            return [b], True
        if b.op_code in ORDERING_OPS:
            inverse_ordering_op = invert_ordered_binary_op(b.op_code)
            return [attrs.evolve(b, op_code=inverse_ordering_op)], True

    match a, b:
        # `frame_dig n; frame_bury n` is redundant
        case models.FrameDig(n=dig_n), models.FrameBury(n=bury_n) if dig_n == bury_n:
            return [], True
        # `frame_bury n; frame_dig n` can be simplified to dup; frame_bury n
        case models.FrameBury(n=dig_n), models.FrameDig(n=bury_n) if dig_n == bury_n:
            return [models.Dup(source_location=None), a], True
        # `dup; swap` -> `dup`
        case models.TealOp(op_code="dup" | "dupn"), maybe_swap if is_stack_swap(maybe_swap):
            return [a], True
        # `dup; pop`
        case models.TealOp(op_code="dup"), models.TealOp(op_code="pop"):
            return [], True
        # combine consecutive dup/dupn's
        case models.TealOp(op_code="dup" | "dupn"), models.TealOp(op_code="dup" | "dupn"):
            (n1,) = a.immediates or (1,)
            assert isinstance(n1, int)
            (n2,) = b.immediates or (1,)
            assert isinstance(n2, int)
            return [models.DupN(n=n1 + n2, source_location=a.source_location)], True
        # combine consecutive pop/popn's
        case models.TealOp(op_code="pop" | "popn"), models.TealOp(op_code="pop" | "popn"):
            (n1,) = a.immediates or (1,)
            assert isinstance(n1, int)
            (n2,) = b.immediates or (1,)
            assert isinstance(n2, int)
            return [models.PopN(n=n1 + n2, source_location=a.source_location)], True
        # `dig 1; dig 1` -> `dup2`
        case models.TealOpUInt8(op_code="dig", n=1), models.TealOpUInt8(op_code="dig", n=1):
            return [models.Dup2(source_location=a.source_location or b.source_location)], True
    return [a, b], False


def _optimize_triplet(
    a: models.TealOp, b: models.TealOp, c: models.TealOp, *, stack_height: int
) -> tuple[list[models.TealOp], bool]:
    if _frame_digs_overlap_with_ops(stack_height, a, b, c):
        return [a, b, c], False

    # `'cover 3; cover 3; swap` -> `uncover 2; uncover 3`
    if (
        is_stack_swap(c)
        and (a.op_code == "cover" and a.immediates[0] == 3)
        and (b.op_code == "cover" and b.immediates[0] == 3)
    ):
        return [
            models.Uncover(n=2, source_location=a.source_location),
            models.Uncover(n=3, source_location=b.source_location),
        ], True

    # `swap; (consumes=0, produces=1); uncover 2` -> `(consume=0, produces=1); swap`
    if (
        is_stack_swap(a)
        and (c.op_code == "uncover" and c.immediates[0] == 2)
        and (
            b.op_code in LOAD_OP_CODES_INCL_OFFSET
            # only count digs if they go below the swap
            and (b.op_code != "dig" or int(b.immediates[0]) >= 2)
        )
    ):
        return [b, a], True

    # <load A>; <load B>; swap -> <load B>; <load A>
    if (
        is_stack_swap(c)
        and a.op_code in LOAD_OP_CODES_INCL_OFFSET
        and b.op_code in LOAD_OP_CODES_INCL_OFFSET
        # cant swap dig 0, which will become a dup anyway
        and (not isinstance(b, models.Dig) or b.n)
    ):
        if isinstance(a, models.Dig):
            a = attrs.evolve(a, n=a.n + 1)
        if isinstance(b, models.Dig):
            new_n = b.n - 1
            if new_n == 0:
                b = models.Dup(source_location=b.source_location)
            else:
                b = attrs.evolve(b, n=new_n)
        return [b, a], True

    # swap; <store A>; <store B> -> <store B>; <store A>
    if (
        is_stack_swap(a)
        and b.op_code in STORE_OPS_INCL_OFFSET
        and c.op_code in STORE_OPS_INCL_OFFSET
    ):
        height_below_swap = stack_height - 2
        if not (
            (b.op_code == "frame_bury" and int(b.immediates[0]) >= height_below_swap)
            or (c.op_code == "frame_bury" and int(c.immediates[0]) >= height_below_swap)
            or (
                # can't swap ops if store order is important
                # e.g. itxn_field ApplicationArgs or frame_bury -1
                b.op_code in ("frame_bury", "itxn_field")
                and b.op_code == c.op_code
                and b.immediates == c.immediates
            )
        ):
            return [c, b], True

    match a, b, c:
        # `uncover 2; swap; uncover 2` is equivalent to `swap`
        case models.Uncover(n=2), maybe_swap, models.Uncover(n=2) if is_stack_swap(maybe_swap):
            return [maybe_swap], True
        # `dup; cover 2; swap` can be replaced by `dup; uncover 2`
        case models.Dup(), models.Cover(n=2), maybe_swap if is_stack_swap(maybe_swap):
            return [
                a,
                models.Uncover(n=2, source_location=b.source_location or c.source_location),
            ], True

    # `uncover n; dup; cover n+1` can be replaced with `dig n`
    # this occurs when the x-stack becomes the l-stack
    if (
        a.op_code == "uncover"
        and b.op_code == "dup"
        and c.op_code == "cover"
        and isinstance((n := a.immediates[0]), int)
        and (n + 1) == c.immediates[0]
    ):
        return [
            models.Dig(
                n=n, source_location=a.source_location or b.source_location or c.source_location
            )
        ], True
    return [a, b, c], False


def _frame_digs_overlap_with_ops(stack_height: int, *ops: models.TealOp) -> bool:
    """
    Check to see if there is a frame_dig in the sequence that could be impacted
    if ops were re-ordered/eliminated/otherwise optimized.
    """
    curr_height = min_stack_height = stack_height
    for op in ops:
        if op.op_code == "frame_dig":
            n = op.immediates[0]
            assert isinstance(n, int)
            if n >= min_stack_height:
                return True
        curr_height -= op.consumes
        min_stack_height = min(curr_height, min_stack_height)
        curr_height += op.produces
    return False


def _optimize_quadruplet(
    a: models.TealOp, b: models.TealOp, c: models.TealOp, d: models.TealOp
) -> tuple[list[models.TealOp], bool]:
    # `swap; <re-orderable load op>; swap; uncover 2` -> `dig|uncover n; cover 2`
    if (
        is_stack_swap(a)
        and (
            b.op_code in LOAD_OP_CODES
            or (b.op_code in ("dig", "uncover") and int(b.immediates[0]) >= 2)
            or (b.op_code == "frame_dig" and int(b.immediates[0]) < 0)
        )
        and is_stack_swap(c)
        and (d.op_code == "uncover" and d.immediates[0] == 2)
    ):
        return [b, models.Cover(n=2, source_location=d.source_location)], True
    return [a, b, c, d], False
