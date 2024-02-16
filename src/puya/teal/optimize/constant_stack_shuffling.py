import functools
import operator

from puya.teal import models
from puya.teal.optimize._data import LOAD_OP_CODES


def perform_constant_stack_shuffling(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if op.op_code in LOAD_OP_CODES:  # noqa: SIM114
            loads.append(op)
        elif isinstance(op, models.FrameDig) and op.n < 0:
            loads.append(op)
        elif loads:
            match op:
                case models.Uncover(n=n) if n < len(loads):
                    modified = True
                    uncovered = loads.pop(-(n + 1))
                    loads.append(uncovered)
                case models.Cover(n=n) if n < len(loads):
                    modified = True
                    to_cover = loads.pop()
                    loads.insert(-n, to_cover)
                case _:
                    result.extend(loads)
                    loads = []
                    result.append(op)
        else:
            result.append(op)
    if loads:
        result.extend(loads)
    block.ops = result
    return modified


def constant_dupn_insertion(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if loads and op == loads[0]:
            loads.append(op)
        else:
            if loads:
                modified = _collapse_loads(loads) or modified
                result.extend(loads)
                loads = []
            if op.op_code in LOAD_OP_CODES or (
                op.op_code == "frame_dig" and int(op.immediates[0]) < 0
            ):
                loads.append(op)
            else:
                result.append(op)
    if loads:
        modified = _collapse_loads(loads) or modified
        result.extend(loads)
    block.ops = result
    return modified


def _collapse_loads(loads: list[models.TealOp]) -> bool:
    n = len(loads) - 1
    if n >= 2:
        dupn_source_location = functools.reduce(
            operator.add, (op.source_location for op in loads[1:])
        )
        loads[1:] = [models.DupN(n=n, source_location=dupn_source_location)]
        return True
    return False
