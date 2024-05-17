import attrs

from puya.teal import models
from puya.teal.optimize._data import LOAD_OP_CODES


def perform_constant_stack_shuffling(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if _is_constant_load(op):
            loads.append(op)
        elif loads and op.op_code in ("dup", "dupn"):
            (n,) = op.immediates or (1,)
            assert isinstance(n, int)
            loads.extend([attrs.evolve(loads[-1], source_location=op.source_location)] * n)
            modified = True
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
            if _is_constant_load(op):
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
    if n < 1:
        return False

    if n == 1:
        dup_op: models.TealOp = models.Dup(source_location=loads[1].source_location)
    else:
        dupn_source_location = None
        for op in loads[1:]:
            if op.source_location is not None:
                # TODO: it'd be better to only merge these if they're adjacent
                dupn_source_location = op.source_location + dupn_source_location
        dup_op = models.DupN(n=n, source_location=dupn_source_location)
    loads[1:] = [dup_op]
    return True


def _is_constant_load(op: models.TealOp) -> bool:
    return op.op_code in LOAD_OP_CODES or (isinstance(op, models.FrameDig) and op.n < 0)
