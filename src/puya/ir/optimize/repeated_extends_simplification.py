from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize._utils import get_byte_constant
from puya.parse import sequential_source_locations_merge

logger = log.get_logger(__name__)


def repeated_extends_simplification(_: CompileContext, subroutine: models.Subroutine) -> bool:
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
        if not maybe_previous_extends:
            continue
        maybe_previous_const_values = get_byte_constant(
            register_assignments, maybe_previous_extends.values
        )
        maybe_current_const_values = get_byte_constant(
            register_assignments, current_extends.values
        )
        if maybe_previous_const_values and maybe_current_const_values:
            # merge extends by updating current extends with combined constants
            # previous extends will be eliminated if no longer used
            current_extends.array = maybe_previous_extends.array
            current_extends.values = models.BytesConstant(
                value=maybe_previous_const_values.value + maybe_current_const_values.value,
                encoding=maybe_previous_const_values.encoding,
                source_location=sequential_source_locations_merge(
                    (
                        maybe_previous_const_values.source_location,
                        maybe_current_const_values.source_location,
                    )
                ),
            )
            modified = True
    return modified
