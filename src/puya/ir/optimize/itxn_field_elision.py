import typing
from collections import defaultdict

import attrs

from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp

_ARRAY_FIELDS: typing.Final = frozenset(
    (
        "ApplicationArgs",
        "Accounts",
        "Assets",
        "Applications",
        "ApprovalProgramPages",
        "ClearStateProgramPages",
    )
)
_ZERO_DEFAULTS: typing.Final = frozenset(
    (
        "ExtraProgramPages",
        "GlobalNumUint",
        "GlobalNumByteSlice",
        "LocalNumUint",
        "LocalNumByteSlice",
    )
)


def elide_itxn_field_calls(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    for block in subroutine.body:
        if _elide_within_block(block):
            modified = True
    return modified


def _elide_within_block(block: models.BasicBlock) -> bool:
    groups = list[_ITxnGroup]()
    current_group: _ITxnGroup | None = None
    for op_idx, op in enumerate(block.ops):
        if isinstance(op, models.Intrinsic):
            match op.op:
                case AVMOp.itxn_begin | AVMOp.itxn_next:
                    groups.append(current_group := _ITxnGroup(has_start=True))
                case AVMOp.itxn_submit:
                    current_group = None
                case AVMOp.itxn_field:
                    (field_im,) = op.immediates
                    assert isinstance(field_im, str)
                    if field_im not in _ARRAY_FIELDS:
                        if current_group is None:
                            groups.append(current_group := _ITxnGroup(has_start=False))
                        current_group.sets[field_im].append(op_idx)
    if not groups:
        return False
    remove_indexes = set[int]()
    for group in groups:
        for field_im, indexes in group.sets.items():
            final_idx = indexes.pop()
            remove_indexes.update(indexes)
            if group.has_start and field_im in _ZERO_DEFAULTS:
                match block.ops[final_idx]:
                    case models.Intrinsic(args=[models.UInt64Constant(value=0)]):
                        remove_indexes.add(final_idx)
    if not remove_indexes:
        return False
    block.ops = [op for idx, op in enumerate(block.ops) if idx not in remove_indexes]
    return True


@attrs.define
class _ITxnGroup:
    has_start: bool
    sets: defaultdict[str, list[int]] = attrs.field(factory=lambda: defaultdict(list))
