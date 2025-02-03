from puya import log
from puya.context import CompileContext
from puya.ir import models

logger = log.get_logger(__name__)


def repeated_extends_simplification(_: CompileContext, subroutine: models.Subroutine) -> bool:
    # TODO: remove this?
    modified = False
    # gather all extends
    extends = dict[models.Value, models.ArrayExtend]()
    register_assignments = dict[models.Register, models.Assignment]()
    for block in subroutine.body:
        for op in block.all_ops:
            if isinstance(op, models.Assignment):
                if isinstance(op.source, models.ArrayExtend):
                    extends[op.targets[0]] = op.source
                if len(op.targets) == 1:
                    (target,) = op.targets
                    register_assignments[target] = op

    # see if any extends can be merged
    for current_extends in extends.values():
        maybe_previous_extends = extends.get(current_extends.array)
        if maybe_previous_extends:
            current_extends.array = maybe_previous_extends.array
            current_extends.values = [*maybe_previous_extends.values, *current_extends.values]
            modified = True
    return modified
